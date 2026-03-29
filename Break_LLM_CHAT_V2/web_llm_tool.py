"""
WebLLMTool — LangChain Tool 래퍼.

LLMChatClient를 LangChain AgentExecutor가 호출할 수 있는 Tool로 래핑합니다.
단일 Selenium 세션을 유지하는 싱글턴 패턴을 사용합니다.
"""

import logging
from typing import Optional

from langchain.tools import Tool

from chat_client import LLMChatClient
from config import AgentConfig
from selector_store import SelectorStore
from trace_logger import TraceLogger

logger = logging.getLogger(__name__)

TOOL_DESCRIPTION = (
    "웹 채팅 인터페이스를 통해 고성능 reasoning LLM에 질의합니다. "
    "복잡한 추론, 코드 생성, 분석, 지식 검색이 필요한 모든 작업에 이 도구를 사용하세요. "
    "입력: 자기 완결적인 질의 문자열. 출력: 모델의 응답 텍스트."
)


class WebLLMTool:
    """LLMChatClient 세션을 관리하고 LangChain Tool로 노출합니다."""

    def __init__(self, config: AgentConfig, tracer: Optional[TraceLogger] = None):
        self._config = config
        self._tracer = tracer
        self._store = SelectorStore(
            cache_file=config.selector_cache_file,
            failure_threshold=config.selector_failure_threshold,
        )
        self._client: Optional[LLMChatClient] = None

    # ------------------------------------------------------------------
    # 세션 관리
    # ------------------------------------------------------------------

    def _ensure_client(self) -> LLMChatClient:
        if self._client is None:
            self._client = LLMChatClient(
                url=self._config.llm_chat_url,
                headless=self._config.llm_chat_headless,
                page_load_wait=self._config.llm_chat_page_load_wait,
                tracer=self._tracer,
                store=self._store,
            )
        return self._client

    def open_and_wait_for_login(self) -> None:
        """브라우저를 열고 수동 로그인을 기다립니다."""
        client = self._ensure_client()
        client.open()
        if self._tracer:
            self._tracer.log("BROWSER_OPENED", url=self._config.llm_chat_url)

        print("\n로그인이 필요하다면 브라우저 창에서 로그인해주세요.")
        input("채팅 페이지가 준비되면 Enter를 누르세요...\n")

        if self._tracer:
            self._tracer.log("LOGIN_CONFIRMED")

    def shutdown(self) -> None:
        """브라우저 세션을 종료합니다. 여러 번 호출해도 안전합니다."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:
                logger.warning("Error closing browser: %s", exc)
            finally:
                self._client = None
            logger.info("Browser session closed.")

    # ------------------------------------------------------------------
    # Tool 호출
    # ------------------------------------------------------------------

    def _query(self, question: str) -> str:
        """LangChain Tool의 실제 구현부."""
        logger.info("WebLLMTool called with %d-char query", len(question))
        if self._tracer:
            self._tracer.log("TOOL_CALL", length=len(question))

        client = self._ensure_client()
        try:
            response = client.send_query(
                query=question,
                config=self._config,  # self-healing을 위해 config 전달
            )
            if self._tracer:
                self._tracer.log("TOOL_RESPONSE", length=len(response))
            return response
        except Exception as exc:
            logger.error("WebLLMTool error: %s", exc)
            if self._tracer:
                self._tracer.log("TOOL_ERROR", error=str(exc))
            return f"[오류] 웹 채팅 LLM 호출에 실패했습니다: {exc}"

    def as_langchain_tool(self) -> Tool:
        """LangChain AgentExecutor에 등록할 Tool 객체를 반환합니다."""
        return Tool(
            name="ThinkingModelQuery",
            description=TOOL_DESCRIPTION,
            func=self._query,
        )
