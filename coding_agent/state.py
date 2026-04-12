from typing import TypedDict, Annotated
import operator


def merge_dicts(old: dict | None, new: dict | None) -> dict:
    """Reducer: merge new keys into old dict."""
    if old is None:
        return new or {}
    if new is None:
        return old
    return {**old, **new}


class AgentState(TypedDict):
    goal: str
    plan: str
    plan_approved: bool
    files: Annotated[dict[str, str], merge_dicts]
    test_code: str
    test_command: str
    logs: Annotated[list[dict], operator.add]
    error_type: str | None
    error_message: str | None
    diagnosis: str | None
    rag_context: str | None
    iteration: int
    max_iterations: int
    done: bool
