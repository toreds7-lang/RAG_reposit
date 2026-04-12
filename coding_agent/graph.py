from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore

from checkpointer import get_checkpointer
from nodes.backend_coder import backend_coder
from nodes.coder import route_to_coder
from nodes.error_analyzer import error_analyzer
from nodes.fixer import fixer
from nodes.frontend_coder import frontend_coder
from nodes.goal_analyzer import goal_analyzer
from nodes.planner import planner
from nodes.rag_retriever import rag_retriever
from nodes.summarizer import summarizer
from nodes.test_writer import test_writer
from nodes.tester import tester
from state import AgentState


def route_after_tester(state: dict) -> str:
    if state.get("done"):
        return "summarizer"
    if state.get("iteration", 0) >= state.get("max_iterations", 5):
        return "summarizer"
    return "error_analyzer"


def route_after_fixer(state: dict) -> str:
    error = state.get("error_type", "")
    if error in ("syntax", "import"):
        return "tester"
    return "planner"


# Module-level store so it persists across multiple graph invocations
_store = InMemoryStore()


def build_graph(store=None):
    if store is None:
        store = _store

    g = StateGraph(AgentState)

    # Add nodes
    g.add_node("goal_analyzer", goal_analyzer)
    g.add_node("rag_retriever", rag_retriever)
    g.add_node("planner", planner)
    g.add_node("backend_coder", backend_coder)
    g.add_node("frontend_coder", frontend_coder)
    g.add_node("test_writer", test_writer)
    g.add_node("tester", tester)
    g.add_node("error_analyzer", error_analyzer)
    g.add_node("fixer", fixer)
    g.add_node("summarizer", summarizer)

    # Linear edges
    g.add_edge(START, "goal_analyzer")
    g.add_edge("goal_analyzer", "rag_retriever")
    g.add_edge("rag_retriever", "planner")

    # Planner → coder router (backend or frontend)
    g.add_conditional_edges("planner", route_to_coder, {
        "backend_coder": "backend_coder",
        "frontend_coder": "frontend_coder",
    })
    g.add_edge("backend_coder", "test_writer")
    g.add_edge("frontend_coder", "summarizer")

    g.add_edge("test_writer", "tester")
    g.add_edge("error_analyzer", "fixer")
    g.add_edge("summarizer", END)

    # Conditional: after tester
    g.add_conditional_edges("tester", route_after_tester, {
        "error_analyzer": "error_analyzer",
        "summarizer": "summarizer",
    })

    # Conditional: after fixer
    g.add_conditional_edges("fixer", route_after_fixer, {
        "tester": "tester",
        "planner": "planner",
    })

    checkpointer = get_checkpointer()
    return g.compile(checkpointer=checkpointer, store=store)
