from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import get_llm, load_prompt
from state import AgentState


def error_analyzer(state: AgentState) -> dict:
    llm = get_llm()
    system_prompt = load_prompt("error_analyzer.txt")

    # Get relevant file content
    files = state.get("files", {})
    code_text = ""
    for fname, content in files.items():
        if not fname.endswith(".md"):
            code_text += f"\n--- {fname} ---\n{content[:3000]}\n"

    user_content = (
        f"에러 종류: {state.get('error_type', 'unknown')}\n"
        f"에러 메시지:\n{(state.get('error_message') or '')[:500]}\n\n"
        f"코드:{code_text}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    result = llm.invoke(messages)

    return {
        "diagnosis": result.content.strip(),
        "logs": [{"node": "error_analyzer", "diagnosis": result.content.strip()[:200]}],
    }
