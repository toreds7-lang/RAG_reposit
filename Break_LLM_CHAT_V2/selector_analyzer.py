"""
Selector 자동 발견 — LLM으로 HTML 분석 후 CSS selector 추출.

페이지 HTML을 헤드리스 브라우저로 가져온 뒤 오케스트레이터 LLM에게 분석을 요청하여
입력창·전송 버튼·로딩 표시자·응답 영역의 CSS selector를 발견합니다.

발견된 selector는:
  1. chat_client 모듈의 모듈 레벨 리스트에 prepend (런타임 패치)
  2. SelectorStore에 저장 (영속 캐시)
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field

from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from config import AgentConfig
from trace_logger import TraceLogger

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """\
You are an expert at reading HTML and identifying CSS selectors for chat UI elements.
Given the HTML of a chat web page, return a JSON object with exactly these four keys:
  input_selectors       — the text input / textarea where the user types a message
  send_button_selectors — the button that submits the message
  loading_indicators    — elements visible ONLY while the model is generating a response
  response_selectors    — elements that contain the assistant / model response text

Each value must be a JSON array of CSS selector strings, ordered from most-specific to most-generic.
Return ONLY valid JSON. No prose, no markdown, no code fences.
"""


@dataclass
class DiscoveredSelectors:
    input_selectors: list = field(default_factory=list)
    send_button_selectors: list = field(default_factory=list)
    loading_indicators: list = field(default_factory=list)
    response_selectors: list = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any([
            self.input_selectors,
            self.send_button_selectors,
            self.loading_indicators,
            self.response_selectors,
        ])


def _strip_scripts_and_styles(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    return html


def _get_page_html(url: str, config: AgentConfig) -> str:
    """헤드리스 Chrome으로 URL을 열고 페이지 소스를 반환합니다."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(url)
        time.sleep(config.llm_chat_page_load_wait)
        return driver.page_source
    finally:
        driver.quit()


def _ask_llm_for_selectors(html: str, config: AgentConfig) -> dict:
    """HTML을 오케스트레이터 LLM에게 보내고 selector dict를 반환합니다."""
    html = _strip_scripts_and_styles(html)
    if len(html) > config.selector_html_max_chars:
        html = html[: config.selector_html_max_chars]
        logger.debug("HTML truncated to %d chars for LLM analysis.", config.selector_html_max_chars)

    client = OpenAI(
        base_url=config.vllm_base_url,
        api_key=config.vllm_api_key,
    )

    user_msg = (
        "Here is the HTML of a company-internal LLM chat web page. "
        "Identify the CSS selectors for the four categories described in the system prompt.\n\n"
        f"HTML:\n{html}"
    )

    for attempt in range(1, 4):
        try:
            response = client.chat.completions.create(
                model=config.vllm_model,
                messages=[
                    {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
                max_tokens=1024,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE)
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Attempt %d: LLM returned invalid JSON: %s", attempt, exc)
        except Exception as exc:
            logger.warning("Attempt %d: LLM request failed: %s", attempt, exc)
            break

    return {}


def _validate_selectors(data: dict) -> DiscoveredSelectors:
    def _clean(key: str) -> list:
        val = data.get(key, [])
        if isinstance(val, list):
            return [s for s in val if isinstance(s, str) and s.strip()]
        return []

    return DiscoveredSelectors(
        input_selectors=_clean("input_selectors"),
        send_button_selectors=_clean("send_button_selectors"),
        loading_indicators=_clean("loading_indicators"),
        response_selectors=_clean("response_selectors"),
    )


def discover_selectors(
    config: AgentConfig,
    tracer: TraceLogger | None = None,
) -> DiscoveredSelectors:
    """
    전체 발견 파이프라인:
    1. 헤드리스 브라우저로 HTML 취득
    2. LLM에게 CSS selector 분석 요청
    3. 결과 검증 후 반환

    실패 시 로그 경고 후 빈 DiscoveredSelectors를 반환하여 내장 selector 목록으로 폴백합니다.
    """
    url = config.llm_chat_url
    logger.info("Starting selector discovery for %s ...", url)
    if tracer:
        tracer.log("DISCOVERY_START", url=url)

    try:
        html = _get_page_html(url, config)
    except Exception as exc:
        logger.warning("Could not fetch page HTML for selector discovery: %s", exc)
        if tracer:
            tracer.log("DISCOVERY_ERROR", stage="fetch_html", error=str(exc))
        return DiscoveredSelectors()

    try:
        raw = _ask_llm_for_selectors(html, config)
    except Exception as exc:
        logger.warning("LLM selector analysis failed: %s", exc)
        if tracer:
            tracer.log("DISCOVERY_ERROR", stage="llm_analysis", error=str(exc))
        return DiscoveredSelectors()

    discovered = _validate_selectors(raw)

    if discovered.is_empty():
        logger.warning("Selector discovery returned no usable selectors; using built-in lists.")
        if tracer:
            tracer.log("DISCOVERY_RESULT", source="llm", status="empty")
    else:
        logger.info(
            "Discovered selectors — input:%d send:%d loading:%d response:%d",
            len(discovered.input_selectors),
            len(discovered.send_button_selectors),
            len(discovered.loading_indicators),
            len(discovered.response_selectors),
        )
        if tracer:
            tracer.log(
                "DISCOVERY_RESULT",
                source="llm",
                input=len(discovered.input_selectors),
                send=len(discovered.send_button_selectors),
                loading=len(discovered.loading_indicators),
                response=len(discovered.response_selectors),
            )

    return discovered


def patch_chat_client_selectors(discovered: DiscoveredSelectors) -> None:
    """
    발견된 selector를 chat_client 모듈의 모듈 레벨 리스트 맨 앞에 삽입합니다.
    Python 리스트는 mutable이므로 chat_client.py 수정 없이 런타임 패치가 가능합니다.
    """
    if discovered.is_empty():
        return

    import chat_client  # 순환 의존 방지를 위해 로컬 import

    if discovered.input_selectors:
        chat_client.INPUT_SELECTORS[:0] = discovered.input_selectors
    if discovered.send_button_selectors:
        chat_client.SEND_BUTTON_SELECTORS[:0] = discovered.send_button_selectors
    if discovered.loading_indicators:
        chat_client.LOADING_INDICATORS[:0] = discovered.loading_indicators
    if discovered.response_selectors:
        chat_client.RESPONSE_SELECTORS[:0] = discovered.response_selectors

    logger.info("chat_client selector lists patched with discovered selectors.")
