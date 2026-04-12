from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import get_llm, load_prompt
from parsers import extract_code_block
from state import AgentState
from tools.file_ops import write_file


def test_writer(state: AgentState) -> dict:
    llm = get_llm()
    system_prompt = load_prompt("test_writer.txt")

    # Get the main code file content
    files = state.get("files", {})
    if not files:
        return {
            "test_code": "",
            "logs": [{"node": "test_writer", "error": "no files to test"}],
        }

    # Use the first (usually only) file
    main_filename = list(files.keys())[0]
    main_code = files[main_filename]

    user_content = f"다음 코드를 테스트하는 pytest 코드를 작성하세요.\n\n코드 ({main_filename}):\n{main_code[:3000]}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    result = llm.invoke(messages)
    test_code = extract_code_block(result.content)

    test_filename = f"test_{main_filename}" if not main_filename.startswith("test_") else main_filename
    write_file(test_filename, test_code)

    return {
        "test_code": test_code,
        "files": {test_filename: test_code},
        "logs": [{"node": "test_writer", "test_filename": test_filename}],
    }
