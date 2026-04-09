import logging
from typing import List
from utils import llm_call, system_prompt

logger = logging.getLogger(__name__)

def write_final_report(
    prompt: str,
    learnings: List[str],
    visited_urls: List[str],
    client,
    model: str,
) -> str:
    """
    모든 연구 결과를 바탕으로 최종 보고서를 생성합니다.
    llm_call을 사용하여 마크다운 보고서를 얻습니다.
    """
    logger.info("write_final_report started | model=%s | learnings=%d | urls=%d",
                model, len(learnings), len(visited_urls))

    learnings_string = ("\n".join([f"<learning>\n{learning}\n</learning>" for learning in learnings])).strip()[:150000]

    user_prompt = (
        f"사용자가 제시한 다음 프롬프트에 대해, 러서치 결과를 바탕으로 최종 보고서를 작성하세요. "
        f"마크다운 형식으로 상세한 보고서(6,000자 이상)를 작성하세요. "
        f"러서치에서 얻은 모든 학습 내용을 포함해야 합니다:\n\n"
        f"<prompt>{prompt}</prompt>\n\n"
        f"다음은 리서치를 통해 얻은 모든 학습 내용입니다:\n\n<learnings>\n{learnings_string}\n</learnings>"
    )
    sys_prompt = system_prompt()
    if sys_prompt:
        user_prompt = f"{sys_prompt}\n\n{user_prompt}"

    logger.info("write_final_report | full prompt length=%d chars", len(user_prompt))

    try:
        report = llm_call(user_prompt, model, client)
        urls_section = "\n\n## 출처\n\n" + "\n".join(f"- {url}" for url in visited_urls)
        logger.info("write_final_report completed | report_length=%d chars", len(report or ""))
        return report + urls_section
    except Exception as e:
        logger.error("write_final_report FAILED | model=%s | error=%s", model, e, exc_info=True)
        print(f"Error generating report: {e}")
        return "Error generating report"
