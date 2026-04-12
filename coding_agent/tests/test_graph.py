"""Integration tests for the graph structure.

Tests graph compilation, node connectivity, and routing logic
without requiring a real LLM (no API calls).
"""
import pytest

from graph import build_graph, route_after_fixer, route_after_tester
from nodes.coder import route_to_coder
from nodes.tester import classify_error
from state import AgentState


class TestGraphCompilation:
    def test_graph_compiles(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self):
        graph = build_graph()
        node_names = list(graph.nodes.keys())
        expected = [
            "goal_analyzer", "rag_retriever", "planner",
            "backend_coder", "frontend_coder",
            "test_writer", "tester",
            "error_analyzer", "fixer", "summarizer",
        ]
        for name in expected:
            assert name in node_names, f"Missing node: {name}"


class TestRouting:
    def test_route_to_backend(self):
        state = {"goal": "Write a function that adds two numbers"}
        assert route_to_coder(state) == "backend_coder"

    def test_route_to_frontend(self):
        state = {"goal": "Create an HTML web page with CSS"}
        assert route_to_coder(state) == "frontend_coder"

    def test_route_to_frontend_korean(self):
        state = {"goal": "웹페이지를 만들어줘"}
        assert route_to_coder(state) == "frontend_coder"

    def test_route_after_tester_done(self):
        state = {"done": True, "iteration": 0, "max_iterations": 5}
        assert route_after_tester(state) == "summarizer"

    def test_route_after_tester_max_iterations(self):
        state = {"done": False, "iteration": 5, "max_iterations": 5}
        assert route_after_tester(state) == "summarizer"

    def test_route_after_tester_error(self):
        state = {"done": False, "iteration": 0, "max_iterations": 5}
        assert route_after_tester(state) == "error_analyzer"

    def test_route_after_fixer_syntax(self):
        state = {"error_type": "syntax"}
        assert route_after_fixer(state) == "tester"

    def test_route_after_fixer_import(self):
        state = {"error_type": "import"}
        assert route_after_fixer(state) == "tester"

    def test_route_after_fixer_test_fail(self):
        state = {"error_type": "test_fail"}
        assert route_after_fixer(state) == "planner"

    def test_route_after_fixer_runtime(self):
        state = {"error_type": "runtime"}
        assert route_after_fixer(state) == "planner"

    def test_route_after_fixer_logic(self):
        state = {"error_type": "logic"}
        assert route_after_fixer(state) == "planner"


class TestErrorClassification:
    def test_all_types(self):
        assert classify_error("OK", 0) == "none"
        assert classify_error("SyntaxError: ...", 1) == "syntax"
        assert classify_error("ModuleNotFoundError: ...", 1) == "import"
        assert classify_error("ImportError: ...", 1) == "import"
        assert classify_error("FAILED test_foo", 1) == "test_fail"
        assert classify_error("Traceback ... TypeError", 1) == "runtime"
        assert classify_error("some output", 1) == "logic"
