from state import AgentState
from tools.exec_ops import run_command


def classify_error(output: str, returncode: int) -> str:
    if returncode == 0:
        return "none"
    if "SyntaxError" in output:
        return "syntax"
    if "ModuleNotFoundError" in output or "ImportError" in output:
        return "import"
    if "AssertionError" in output or "AssertError" in output or "FAILED" in output:
        return "test_fail"
    if "Traceback" in output:
        return "runtime"
    return "logic"


def tester(state: AgentState) -> dict:
    test_command = state.get("test_command", "python -m pytest test_solution.py -v")

    stdout, stderr, returncode = run_command(test_command)
    combined = stdout + "\n" + stderr

    error_type = classify_error(combined, returncode)

    return {
        "error_type": error_type,
        "error_message": combined[:500] if error_type != "none" else None,
        "done": error_type == "none",
        "logs": [
            {
                "node": "tester",
                "returncode": returncode,
                "error_type": error_type,
                "output": combined[:300],
            }
        ],
    }
