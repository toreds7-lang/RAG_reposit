from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import get_llm, load_prompt
from parsers import extract_code_block, extract_filename
from state import AgentState
from tools.file_ops import write_file


def fixer(state: AgentState) -> dict:
    llm = get_llm()
    system_prompt = load_prompt("fixer.txt")

    # Find the main code file (not test, not .md)
    files = state.get("files", {})
    target_file = None
    target_content = ""
    for fname, content in files.items():
        if not fname.startswith("test_") and not fname.endswith(".md"):
            target_file = fname
            target_content = content
            break

    if not target_file:
        # Fallback: use first file
        target_file = list(files.keys())[0] if files else "solution.py"
        target_content = files.get(target_file, "")

    user_content = (
        f"에러 원인: {state.get('diagnosis', 'unknown')}\n\n"
        f"코드 ({target_file}):\n{target_content[:3000]}\n\n"
        f"수정된 전체 코드를 코드블록 안에 작성하세요."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    result = llm.invoke(messages)
    fixed_code = extract_code_block(result.content)

    write_file(target_file, fixed_code)

    new_iteration = state.get("iteration", 0) + 1

    return {
        "files": {target_file: fixed_code},
        "iteration": new_iteration,
        "logs": [
            {
                "node": "fixer",
                "fixed_file": target_file,
                "iteration": new_iteration,
            }
        ],
    }
