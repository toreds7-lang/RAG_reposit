from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import get_llm, load_prompt
from parsers import extract_code_block, extract_filename
from state import AgentState
from tools.file_ops import write_file


def backend_coder(state: AgentState) -> dict:
    llm = get_llm()
    system_prompt = load_prompt("backend_coder.txt")

    user_content = f"계획:\n{state['plan']}"

    rag = state.get("rag_context")
    if rag:
        user_content += f"\n\n참고 코드:\n{rag[:2000]}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    result = llm.invoke(messages)
    text = result.content

    filename = extract_filename(text)
    code = extract_code_block(text)
    write_file(filename, code)

    return {
        "files": {filename: code},
        "logs": [{"node": "backend_coder", "filename": filename}],
    }
