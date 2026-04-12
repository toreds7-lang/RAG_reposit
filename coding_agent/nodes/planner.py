from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from llm_config import get_llm, load_prompt
from state import AgentState
from tools.plan_ops import write_plan_md


def planner(state: AgentState, config, *, store) -> dict:
    llm = get_llm()
    system_prompt = load_prompt("planner.txt")

    user_content = f"목표: {state['goal']}\n요구사항:\n{state['plan']}"

    # Include past lessons from Store
    if store is not None:
        try:
            past_lessons = store.search(namespace=("lessons",), query=state["goal"], limit=3)
            if past_lessons:
                lesson_text = "\n".join(
                    f"- {item.value.get('lesson', '')}" for item in past_lessons
                )
                user_content += f"\n\n과거 학습 내용:\n{lesson_text}"
        except Exception:
            pass  # Store search failure is non-critical

    # Include RAG context if available
    rag = state.get("rag_context")
    if rag:
        user_content += f"\n\n참고 코드:\n{rag[:2000]}"

    # Include error info on re-entry
    if state.get("error_type") and state["error_type"] != "none":
        user_content += f"\n\n이전 에러 ({state['error_type']}): {state.get('diagnosis', '')}"
        user_content += f"\n반복 횟수: {state.get('iteration', 0)}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    result = llm.invoke(messages)
    plan_text = result.content.strip()

    write_plan_md(plan_text)

    # Human-in-the-loop: interrupt for plan approval
    approval = interrupt({
        "plan": plan_text,
        "question": "이 계획을 승인하시겠습니까? (approve/modify/reject)",
    })

    # Handle user response
    if isinstance(approval, dict):
        action = approval.get("action", "approve")
        if action == "modify":
            plan_text = approval.get("modified_plan", plan_text)
            write_plan_md(plan_text)
        elif action == "reject":
            plan_text = "사용자가 계획을 거부했습니다. 재계획 필요."
    # If approval is a string (simple "approve"), just continue

    return {
        "plan": plan_text,
        "plan_approved": True,
        "logs": [{"node": "planner", "iteration": state.get("iteration", 0)}],
    }
