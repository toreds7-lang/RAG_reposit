from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import get_llm, load_prompt
from state import AgentState


def _extract_error_patterns(logs: list[dict]) -> list[str]:
    """Extract unique error types from logs."""
    patterns = []
    for log in logs:
        if log.get("node") == "tester" and log.get("error_type", "none") != "none":
            patterns.append(log["error_type"])
    return list(set(patterns))


def summarizer(state: AgentState, config, *, store) -> dict:
    llm = get_llm()
    system_prompt = load_prompt("summarizer.txt")

    error_patterns = _extract_error_patterns(state.get("logs", []))
    error_logs = [
        log for log in state.get("logs", [])
        if log.get("node") in ("tester", "error_analyzer", "fixer")
    ]
    # Truncate error logs for prompt
    error_summary = "\n".join(
        f"- {log.get('node')}: {str(log)[:150]}"
        for log in error_logs[-5:]  # last 5 error-related logs
    )

    user_content = (
        f"목표: {state['goal']}\n"
        f"반복 횟수: {state.get('iteration', 0)}\n"
        f"성공 여부: {'성공' if state.get('done') else '실패'}\n"
        f"에러 패턴: {', '.join(error_patterns) if error_patterns else '없음'}\n"
        f"에러 로그:\n{error_summary if error_summary else '없음'}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    result = llm.invoke(messages)
    lesson = result.content.strip()

    # Save to Store
    if store is not None:
        try:
            store.put(
                namespace=("lessons",),
                key=f"lesson_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                value={
                    "goal": state["goal"],
                    "lesson": lesson,
                    "iterations": state.get("iteration", 0),
                    "success": state.get("done", False),
                    "error_patterns": error_patterns,
                },
            )
        except Exception:
            pass  # Store write failure is non-critical

    return {
        "logs": [{"node": "summarizer", "lesson": lesson[:200]}],
    }
