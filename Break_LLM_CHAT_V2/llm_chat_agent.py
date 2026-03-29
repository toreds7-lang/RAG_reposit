"""
LangChain Agent 오케스트레이터 (V2).

사내 API LLM(낮은 성능)이 LangChain AgentExecutor로 전체 흐름을 제어하고,
Selenium을 통해 웹 채팅 고성능 LLM(reasoning 포함)에 실제 작업을 위임합니다.

Usage:
    # 단일 질의
    python llm_chat_agent.py --query "CAP 정리를 설명해줘"

    # 대화형 REPL
    python llm_chat_agent.py --interactive

    # selector 자동 발견 건너뛰기
    python llm_chat_agent.py --skip-discovery --query "안녕"
"""

import atexit
import argparse
import logging
import sys
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain import hub

from config import AgentConfig, load_config
from selector_analyzer import discover_selectors, patch_chat_client_selectors
from selector_store import SelectorStore
from trace_logger import TraceLogger
from web_llm_tool import WebLLMTool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are an orchestrating agent. You have access to a tool called ThinkingModelQuery \
that connects to a high-quality reasoning model via a web interface.

Your role:
- Analyze the user's request and break it into clear reasoning steps.
- For any step that requires real reasoning, analysis, code generation, or knowledge retrieval, \
  delegate it to the ThinkingModelQuery tool with a clear, self-contained sub-query.
- Synthesize the tool's response(s) into a final, concise answer for the user.
- Do NOT attempt to answer complex questions from your own knowledge alone — \
  your reasoning capability is limited. Always use ThinkingModelQuery for substantive tasks.

When calling ThinkingModelQuery:
- Provide a self-contained prompt that includes all necessary context.
- Be specific and clear about what you want the thinking model to produce.
"""


class LLMChatAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self._tracer: Optional[TraceLogger] = None
        self._tool_wrapper: Optional[WebLLMTool] = None
        self._agent_executor: Optional[AgentExecutor] = None
        self._query_count = 0
        self._heal_count = 0

    # ------------------------------------------------------------------
    # Agent 구성
    # ------------------------------------------------------------------

    def _build_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            base_url=self.config.vllm_base_url,
            model=self.config.vllm_model,
            api_key=self.config.vllm_api_key,
            temperature=0,
        )

    def _build_agent(self) -> AgentExecutor:
        llm = self._build_llm()
        tools = [self._tool_wrapper.as_langchain_tool()]

        use_react = self.config.agent_use_react.lower()

        if use_react == "true":
            agent = self._make_react_agent(llm, tools)
        elif use_react == "false":
            agent = self._make_tool_calling_agent(llm, tools)
        else:
            # "auto": tool-calling 시도, 실패 시 ReAct로 폴백
            try:
                agent = self._make_tool_calling_agent(llm, tools)
                logger.info("Using tool-calling agent.")
            except Exception as exc:
                logger.warning("tool-calling agent setup failed (%s); falling back to ReAct.", exc)
                agent = self._make_react_agent(llm, tools)
                logger.info("Using ReAct agent.")

        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=self.config.agent_verbose,
            max_iterations=self.config.agent_max_iterations,
            handle_parsing_errors=True,
        )

    def _make_tool_calling_agent(self, llm, tools):
        prompt = ChatPromptTemplate.from_messages([
            ("system", ORCHESTRATOR_SYSTEM_PROMPT),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        return create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)

    def _make_react_agent(self, llm, tools):
        try:
            prompt = hub.pull("hwchase17/react")
        except Exception:
            from langchain.prompts import PromptTemplate
            prompt = PromptTemplate.from_template(
                "Answer the following questions as best you can. "
                "You have access to the following tools:\n\n{tools}\n\n"
                "Use the following format:\n\n"
                "Question: the input question you must answer\n"
                "Thought: you should always think about what to do\n"
                "Action: the action to take, should be one of [{tool_names}]\n"
                "Action Input: the input to the action\n"
                "Observation: the result of the action\n"
                "... (this Thought/Action/Action Input/Observation can repeat N times)\n"
                "Thought: I now know the final answer\n"
                "Final Answer: the final answer to the original input question\n\n"
                "Begin!\n\nQuestion: {input}\n"
                "Thought:{agent_scratchpad}"
            )
        return create_react_agent(llm=llm, tools=tools, prompt=prompt)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def startup(self, wait_for_login: bool = True, skip_discovery: bool = False):
        """
        시작 시퀀스:
        1. TraceLogger 초기화
        2. (선택) CSS selector 자동 발견
        3. 캐시에서 selector 로드 및 적용
        4. 브라우저 열기 및 로그인 대기
        5. AgentExecutor 빌드
        6. atexit 정리 등록
        """
        # 1. TraceLogger 초기화
        self._tracer = TraceLogger(self.config.trace_log_dir)
        self._tracer.log("SESSION_START", url=self.config.llm_chat_url, session=self._tracer.session_id)
        logger.info("Trace log: %s", self._tracer.session_file)

        # SelectorStore 초기화
        store = SelectorStore(
            cache_file=self.config.selector_cache_file,
            failure_threshold=self.config.selector_failure_threshold,
        )

        # 2. Selector 자동 발견 또는 캐시 로드
        if not skip_discovery and self.config.selector_discovery_enabled:
            # 캐시에 이미 저장된 selector가 있으면 우선 적용
            cached = store.load(self.config.llm_chat_url)
            if cached:
                logger.info("Loading selectors from cache.")
                self._tracer.log("CACHE_HIT", url=self.config.llm_chat_url)
                from selector_analyzer import DiscoveredSelectors, patch_chat_client_selectors
                discovered = DiscoveredSelectors(
                    input_selectors=cached["input_selectors"],
                    send_button_selectors=cached["send_button_selectors"],
                    loading_indicators=cached["loading_indicators"],
                    response_selectors=cached["response_selectors"],
                )
                patch_chat_client_selectors(discovered)
            else:
                # 새로 발견
                logger.info("Running selector auto-discovery...")
                discovered = discover_selectors(self.config, tracer=self._tracer)
                patch_chat_client_selectors(discovered)
                if not discovered.is_empty():
                    store.save(self.config.llm_chat_url, discovered)
                    self._tracer.log("CACHE_SAVED", url=self.config.llm_chat_url)
        else:
            logger.info("Selector discovery skipped.")
            self._tracer.log("DISCOVERY_SKIPPED")

        # 3. WebLLMTool 초기화
        self._tool_wrapper = WebLLMTool(config=self.config, tracer=self._tracer)

        # 4. 브라우저 열기
        if wait_for_login:
            self._tool_wrapper.open_and_wait_for_login()
        else:
            self._tool_wrapper._ensure_client().open()

        # 5. AgentExecutor 빌드
        logger.info("Building LangChain agent...")
        self._agent_executor = self._build_agent()

        atexit.register(self.shutdown)
        logger.info("Agent ready.")
        self._tracer.log("AGENT_READY")

    def run(self, user_query: str) -> str:
        """user_query를 에이전트로 실행하고 최종 답변을 반환합니다."""
        if self._agent_executor is None:
            raise RuntimeError("startup()을 먼저 호출하세요.")

        self._query_count += 1
        if self._tracer:
            self._tracer.log("AGENT_RUN", query_idx=self._query_count, length=len(user_query))

        result = self._agent_executor.invoke({"input": user_query})
        answer = result.get("output", "")

        if self._tracer:
            self._tracer.log("AGENT_DONE", query_idx=self._query_count, answer_length=len(answer))

        return answer

    def shutdown(self):
        """브라우저를 닫습니다. 여러 번 호출해도 안전합니다 (atexit 등록됨)."""
        if self._tool_wrapper:
            self._tool_wrapper.shutdown()
        if self._tracer:
            self._tracer.log(
                "SESSION_END",
                total_queries=self._query_count,
            )
            logger.info("Trace log saved: %s", self._tracer.session_file)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args():
    parser = argparse.ArgumentParser(
        description="사내 API LLM이 웹 채팅 고성능 LLM을 Selenium으로 제어하는 오케스트레이터."
    )
    parser.add_argument("--vllm-url", help="오케스트레이터 LLM base URL (VLLM_BASE_URL 환경변수 덮어쓰기)")
    parser.add_argument("--vllm-model", help="오케스트레이터 모델명 (VLLM_MODEL 환경변수 덮어쓰기)")
    parser.add_argument("--llm-chat-url", help="웹 채팅 LLM URL (LLM_CHAT_URL 환경변수 덮어쓰기)")
    parser.add_argument("--headless", action="store_true", help="헤드리스 모드로 브라우저 실행")
    parser.add_argument(
        "--no-wait-for-login",
        action="store_true",
        help="로그인 대기 없이 바로 실행 (세션 쿠키가 이미 있는 경우)",
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="CSS selector 자동 발견 건너뛰기 (내장 목록 사용)",
    )
    parser.add_argument("--query", help="단일 질의 모드: 이 질의를 전송하고 종료")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="대화형 REPL 모드 시작 (--query 없을 때 기본값)",
    )
    return parser.parse_args()


def main():
    args = _parse_args()

    import os
    if args.vllm_url:
        os.environ["VLLM_BASE_URL"] = args.vllm_url
    if args.vllm_model:
        os.environ["VLLM_MODEL"] = args.vllm_model
    if args.llm_chat_url:
        os.environ["LLM_CHAT_URL"] = args.llm_chat_url
    if args.headless:
        os.environ["LLM_CHAT_HEADLESS"] = "true"

    try:
        config = load_config()
    except ValueError as exc:
        print(f"설정 오류: {exc}", file=sys.stderr)
        sys.exit(1)

    agent = LLMChatAgent(config)
    agent.startup(
        wait_for_login=not args.no_wait_for_login,
        skip_discovery=args.skip_discovery,
    )

    if args.query:
        print(f"\n질의: {args.query}")
        print("\n--- 응답 ---")
        print(agent.run(args.query))
        print("------------")
    else:
        print("\n대화형 모드 시작. 종료하려면 'exit' 또는 'quit'을 입력하세요.\n")
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n종료합니다.")
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break
            answer = agent.run(user_input)
            print(f"\nAgent: {answer}\n")

    agent.shutdown()


if __name__ == "__main__":
    main()
