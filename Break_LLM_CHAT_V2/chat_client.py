"""
LLM Chat Client (V2) — Selenium 기반 웹 채팅 자동화.

V1 대비 추가 기능:
  - TraceLogger: 모든 단계(selector 시도, 응답 수신 등)를 trace_log/*.txt에 기록
  - SelectorStore: selector 실패 카운터 관리
  - Self-healing: 실패 횟수가 threshold에 도달하면 selector를 자동 재발견 후 재시도

Usage:
    python chat_client.py --url http://internal-llm/ --query "CAP 정리를 설명해줘"
"""

import time
import argparse
import logging
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from trace_logger import TraceLogger
from selector_store import SelectorStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Selector lists — 가장 구체적인 것부터 일반적인 순서로 정렬.
# discover_selectors() 호출 시 발견된 selector가 맨 앞에 prepend됩니다.
# ---------------------------------------------------------------------------

INPUT_SELECTORS = [
    "#prompt-textarea",                           # ChatGPT
    "textarea[data-id='root']",                   # 구형 ChatGPT
    "div[contenteditable='true'][role='textbox']",
    "textarea[placeholder]",
    "div[contenteditable='true']",
    "textarea",
    "input[type='text'][placeholder]",
]

SEND_BUTTON_SELECTORS = [
    "button[data-testid='send-button']",          # ChatGPT
    "button[aria-label='Send message']",
    "button[aria-label*='Send']",
    "button[type='submit']",
]

LOADING_INDICATORS = [
    "button[data-testid='stop-button']",          # ChatGPT "Stop generating"
    "button[aria-label='Stop generating']",
    "button[aria-label*='Stop']",
    "[class*='loading']",
    "[class*='generating']",
    "[class*='spinner']",
]

RESPONSE_SELECTORS = [
    "[data-message-author-role='assistant']",     # ChatGPT
    "[data-role='assistant']",
    "[class*='assistant-message']",
    "[class*='bot-message']",
    "[class*='ai-message']",
    "[class*='response']",
]


class SelectorNeedHeal(Exception):
    """Selector 실패 횟수가 threshold에 도달했을 때 self-healing을 요청하는 신호."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class LLMChatClient:
    def __init__(
        self,
        url: str,
        headless: bool = False,
        page_load_wait: int = 3,
        tracer: Optional[TraceLogger] = None,
        store: Optional[SelectorStore] = None,
    ):
        self.url = url
        self.page_load_wait = page_load_wait
        self._tracer = tracer
        self._store = store

        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 30)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def open(self):
        self.driver.get(self.url)
        time.sleep(self.page_load_wait)

    def close(self):
        self.driver.quit()

    # ------------------------------------------------------------------
    # Element detection helpers
    # ------------------------------------------------------------------

    def _find_visible(self, selectors: list[str], selector_type: str = ""):
        """
        selector 목록에서 첫 번째 visible 요소를 반환합니다.
        각 시도 결과를 TraceLogger에 기록합니다.
        """
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        if self._tracer and selector_type:
                            self._tracer.log(
                                "SELECTOR_TRY",
                                type=selector_type,
                                selector=selector,
                                result="FOUND",
                            )
                        return el
            except Exception:
                continue
        return None

    def _find_all_visible(self, selectors: list[str]) -> list:
        found = []
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                found.extend([el for el in elements if el.is_displayed()])
            except Exception:
                continue
        return found

    def find_input(self):
        el = self._find_visible(INPUT_SELECTORS, selector_type="input")
        if el is None:
            # 실패 카운터 증가
            failures = 0
            if self._store:
                failures = self._store.mark_failure(self.url)
                if self._tracer:
                    self._tracer.log("SELECTOR_FAIL", type="input", total_failures=failures)
                if self._store.should_rediscover(self.url):
                    raise SelectorNeedHeal("input_not_found")
            raise RuntimeError(
                "Could not find a chat input field. "
                "Add a matching selector to INPUT_SELECTORS or enable selector discovery."
            )
        return el

    def find_send_button(self):
        return self._find_visible(SEND_BUTTON_SELECTORS, selector_type="send_button")

    def get_last_response_text(self) -> str:
        """마지막 어시스턴트 메시지 텍스트를 반환합니다. 없으면 빈 문자열."""
        elements = self._find_all_visible(RESPONSE_SELECTORS)
        if not elements:
            return ""
        try:
            return elements[-1].text.strip()
        except StaleElementReferenceException:
            return ""

    # ------------------------------------------------------------------
    # Self-healing
    # ------------------------------------------------------------------

    def _self_heal(self, config) -> None:
        """
        selector 재발견을 실행하고 모듈 레벨 selector 목록을 패치합니다.
        성공 시 store의 실패 카운터를 초기화합니다.
        """
        from selector_analyzer import discover_selectors, patch_chat_client_selectors

        if self._tracer:
            self._tracer.log("SELF_HEAL_START")

        logger.info("Self-healing: re-discovering selectors for %s", self.url)
        discovered = discover_selectors(config, tracer=self._tracer)
        patch_chat_client_selectors(discovered)

        new_count = sum([
            len(discovered.input_selectors),
            len(discovered.send_button_selectors),
            len(discovered.loading_indicators),
            len(discovered.response_selectors),
        ])

        if self._store:
            if not discovered.is_empty():
                self._store.save(self.url, discovered)
            self._store.reset_failures(self.url)

        if self._tracer:
            self._tracer.log(
                "SELF_HEAL_DONE",
                new_selectors=new_count,
                source="llm" if not discovered.is_empty() else "builtin",
            )

        logger.info("Self-healing complete. New selectors: %d", new_count)

    # ------------------------------------------------------------------
    # Sending a message and waiting for the reply
    # ------------------------------------------------------------------

    def _type_into_element(self, element, text: str):
        """<textarea>와 contenteditable <div> 모두 지원합니다."""
        tag = element.tag_name.lower()
        element.click()
        time.sleep(0.2)
        if tag in ("textarea", "input"):
            element.clear()
            element.send_keys(text)
        else:
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(text)

    def _wait_for_response(self, previous_text: str, timeout: int = 90) -> str:
        """
        모델 응답 완료까지 대기합니다.

        Phase 1: 로딩 표시자 출현 감지 (생성 시작)
        Phase 2: 로딩 표시자 소멸 대기 (생성 완료)
        Phase 3: 텍스트 안정화 확인 (~2초간 변화 없음)
        """
        deadline = time.time() + timeout
        loading_appeared = False

        # Phase 1
        while time.time() < deadline:
            if self._find_visible(LOADING_INDICATORS, selector_type="loading"):
                loading_appeared = True
                if self._tracer:
                    self._tracer.log("LOADING_DETECTED")
                break
            current = self.get_last_response_text()
            if current and current != previous_text:
                break
            time.sleep(0.3)

        if loading_appeared:
            # Phase 2
            while time.time() < deadline:
                if not self._find_visible(LOADING_INDICATORS):
                    break
                time.sleep(0.5)

        # Phase 3: 안정화
        stable_ticks = 0
        last_text = ""
        while time.time() < deadline:
            current = self.get_last_response_text()
            if current and current == last_text:
                stable_ticks += 1
                if stable_ticks >= 4:   # ~2초간 안정
                    return current
            else:
                stable_ticks = 0
            last_text = current
            time.sleep(0.5)

        return last_text

    def send_query(self, query: str, timeout: int = 90, config=None) -> str:
        """
        query를 채팅 입력창에 입력하고 응답을 반환합니다.

        config가 제공된 경우 self-healing이 활성화됩니다.
        SelectorNeedHeal 발생 시 selector를 재발견하고 1회 재시도합니다.
        """
        start_time = time.time()

        if self._tracer:
            self._tracer.log("QUERY_SEND", length=len(query))

        previous_text = self.get_last_response_text()

        try:
            input_el = self.find_input()
        except SelectorNeedHeal as exc:
            if config is None:
                raise RuntimeError(
                    f"Selector heal needed ({exc.reason}) but no config provided to send_query()."
                ) from exc
            if self._tracer:
                self._tracer.log("SELF_HEAL_TRIGGER", reason=exc.reason)
            self._self_heal(config)
            input_el = self._find_visible(INPUT_SELECTORS, selector_type="input")
            if input_el is None:
                raise RuntimeError(
                    "Self-healing completed but input field is still not found."
                )

        self._type_into_element(input_el, query)
        time.sleep(0.3)

        send_btn = self.find_send_button()
        if send_btn and send_btn.is_enabled():
            send_btn.click()
        else:
            input_el.send_keys(Keys.RETURN)

        response = self._wait_for_response(previous_text, timeout=timeout)
        elapsed = round(time.time() - start_time, 1)

        if self._tracer:
            self._tracer.log(
                "RESPONSE_RECEIVED",
                length=len(response),
                elapsed_s=elapsed,
            )

        return response


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="LLM 웹 채팅 인터페이스에 Selenium으로 질의를 전송합니다."
    )
    parser.add_argument("--url", default="https://chatgpt.com/", help="웹 채팅 URL")
    parser.add_argument("--query", default="What is the capital of France?", help="전송할 질의")
    parser.add_argument("--headless", action="store_true", help="헤드리스 모드로 실행")
    parser.add_argument(
        "--no-wait-for-login",
        action="store_true",
        help="로그인 대기 없이 바로 질의 전송",
    )
    parser.add_argument(
        "--trace-dir",
        default="trace_log",
        help="trace 로그 저장 디렉토리 (기본: trace_log)",
    )
    args = parser.parse_args()

    tracer = TraceLogger(args.trace_dir)
    tracer.log("SESSION_START", url=args.url, session=tracer.session_id)

    client = LLMChatClient(
        url=args.url,
        headless=args.headless,
        tracer=tracer,
    )

    print(f"Opening {args.url} ...")
    client.open()

    if not args.no_wait_for_login:
        print("\n로그인이 필요하다면 브라우저 창에서 로그인해주세요.")
        input("채팅 페이지가 준비되면 Enter를 누르세요...\n")

    print(f"질의 전송: {args.query!r}")
    response = client.send_query(args.query)

    print("\n--- 응답 ---")
    print(response)
    print("------------")
    print(f"\nTrace 로그: {tracer.session_file}")

    tracer.log("SESSION_END", total_queries=1)
    client.close()


if __name__ == "__main__":
    main()
