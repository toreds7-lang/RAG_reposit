import re

from langchain_core.messages import HumanMessage, SystemMessage

from llm_config import get_llm, load_prompt
from state import AgentState


def goal_analyzer(state: AgentState) -> dict:
    llm = get_llm()
    system_prompt = load_prompt("analyzer.txt")

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"사용자의 목표: {state['goal']}"),
    ]
    result = llm.invoke(messages)
    text = result.content

    # Parse TEST_COMMAND from last line
    test_command = "python -m pytest test_solution.py -v"
    match = re.search(r"TEST_COMMAND:\s*(.+)", text)
    if match:
        test_command = match.group(1).strip()
        # Remove TEST_COMMAND line from plan
        plan_text = text[: match.start()].strip()
    else:
        plan_text = text.strip()

    return {
        "plan": plan_text,
        "test_command": test_command,
        "logs": [{"node": "goal_analyzer", "plan_length": len(plan_text)}],
    }
