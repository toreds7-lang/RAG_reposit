# -------------------------------
# LLM Helper Functions
# -------------------------------

import logging
import os
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage


def setup_logging() -> None:
    """콘솔(INFO) + 파일(DEBUG) 이중 출력 로깅을 설정합니다. main()에서 한 번만 호출하세요."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return  # 중복 핸들러 방지
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    os.makedirs("output", exist_ok=True)
    file_handler = logging.FileHandler("output/debug.log", mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


logger = logging.getLogger(__name__)


def system_prompt() -> str:
    """현재 타임스탬프를 포함한 시스템 프롬프트를 생성합니다."""
    now = datetime.now().isoformat()
    return f"""당신은 전문 연구원입니다. 오늘 날짜는 {now}입니다. 응답 시 다음 지침을 따르세요:
    - 지식 컷오프 이후의 주제에 대한 조사를 요청받을 수 있습니다. 사용자가 뉴스 내용을 제시했다면, 그것을 사실로 가정하세요.
    - 사용자는 매우 숙련된 분석가이므로 내용을 단순화할 필요 없이 가능한 한 자세하고 정확하게 응답하세요.
    - 체계적으로 정보를 정리하세요.
    - 사용자가 생각하지 못한 해결책을 제안하세요.
    - 적극적으로 사용자의 필요를 예측하고 대응하세요.
    - 사용자를 모든 분야의 전문가로 대우하세요.
    - 실수는 신뢰를 저하시킵니다. 정확하고 철저하게 응답하세요.
    - 상세한 설명을 제공하세요. 사용자는 많은 정보를 받아들일 수 있습니다.
    - 권위보다 논리적 근거를 우선하세요. 출처 자체는 중요하지 않습니다.
    - 기존의 통념뿐만 아니라 최신 기술과 반대 의견도 고려하세요.
    - 높은 수준의 추측이나 예측을 포함할 수 있습니다. 단, 이를 명확히 표시하세요."""


def llm_call(prompt: str, model: str) -> str:
    """주어진 프롬프트로 LLM을 동기적으로 호출합니다."""
    logger.info("llm_call started | model=%s | prompt_length=%d chars", model, len(prompt))
    logger.debug("llm_call prompt (first 500 chars): %.500s", prompt)

    llm = ChatOpenAI(model=model)
    result = llm.invoke([HumanMessage(content=prompt)])

    print(model, "완료")
    content = result.content
    logger.info("llm_call completed | model=%s | response_length=%d chars", model, len(content or ""))
    return content


def JSON_llm(user_prompt: str, schema: BaseModel, system_prompt: Optional[str] = None, model: Optional[str] = None):
    """
    JSON 모드에서 언어 모델 호출을 실행하고 구조화된 JSON 객체를 반환합니다.
    LangChain with_structured_output을 사용합니다.
    """
    if model is None:
        model = "gpt-4o-mini"
    logger.debug("JSON_llm called | model=%s | schema=%s", model, schema.__name__)
    logger.debug("JSON_llm prompt (first 500 chars): %.500s", user_prompt)
    try:
        llm = ChatOpenAI(model=model)
        structured_llm = llm.with_structured_output(schema)

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_prompt))

        parsed = structured_llm.invoke(messages)
        logger.debug("JSON_llm parsed result type: %s", type(parsed).__name__)
        return parsed
    except Exception as e:
        logger.error(
            "JSON_llm FAILED | model=%s | schema=%s | error=%s",
            model, schema.__name__, e,
            exc_info=True
        )
        return None


def get_embeddings(model: str = "text-embedding-3-small") -> OpenAIEmbeddings:
    """OpenAI 임베딩 모델 인스턴스를 반환합니다."""
    return OpenAIEmbeddings(model=model)
