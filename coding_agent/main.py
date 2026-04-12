import sys
from pathlib import Path

from langgraph.types import Command

from checkpointer import get_thread_config
from graph import build_graph


def handle_interrupt(interrupt_data: dict) -> dict:
    """Handle human-in-the-loop interrupt from planner node."""
    print(f"\n{'='*60}")
    print("  PLAN REVIEW (Human-in-the-loop)")
    print(f"{'='*60}")
    print(interrupt_data.get("plan", ""))
    print(f"{'='*60}")

    choice = input("\n  승인(y) / 수정(m) / 거부(n) [y]: ").strip().lower()

    if choice == "m":
        print("  수정할 계획을 입력하세요 (빈 줄 2번으로 종료):")
        lines = []
        empty_count = 0
        while empty_count < 2:
            line = input()
            if line == "":
                empty_count += 1
            else:
                empty_count = 0
            lines.append(line)
        modified_plan = "\n".join(lines).strip()
        return {"action": "modify", "modified_plan": modified_plan}
    elif choice == "n":
        return {"action": "reject"}
    else:
        return {"action": "approve"}


def main():
    if len(sys.argv) > 1:
        goal = " ".join(sys.argv[1:])
    else:
        goal = input("Enter your coding goal: ")

    Path("workspace").mkdir(exist_ok=True)

    graph = build_graph()
    config = get_thread_config()

    initial_state = {
        "goal": goal,
        "plan": "",
        "plan_approved": False,
        "files": {},
        "test_code": "",
        "test_command": "",
        "logs": [],
        "error_type": None,
        "error_message": None,
        "diagnosis": None,
        "rag_context": None,
        "iteration": 0,
        "max_iterations": 5,
        "done": False,
    }

    print(f"\n{'='*60}")
    print(f"  Coding Agent - Goal: {goal}")
    print(f"{'='*60}\n")

    # Run graph with interrupt handling loop
    input_data = initial_state

    while True:
        has_interrupt = False

        for event in graph.stream(input_data, config=config, stream_mode="updates"):
            for node_name, updates in event.items():
                print(f"\n--- [{node_name}] ---")
                if not isinstance(updates, dict):
                    continue
                if "logs" in updates:
                    for log in updates["logs"]:
                        for k, v in log.items():
                            if k != "node":
                                print(f"  {k}: {str(v)[:200]}")
                if updates.get("done"):
                    print("\n  SUCCESS!")
                if node_name == "tester" and not updates.get("done"):
                    error_type = updates.get("error_type", "")
                    if error_type and error_type != "none":
                        print(f"  -> Error detected: {error_type}")

        # Check for interrupt
        state = graph.get_state(config)
        if state.tasks:
            # There's a pending interrupt
            for task in state.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    interrupt_value = task.interrupts[0].value
                    user_response = handle_interrupt(interrupt_value)
                    # Resume with user response
                    input_data = Command(resume=user_response)
                    has_interrupt = True
                    break

        if not has_interrupt:
            break

    # Print final result
    print(f"\n{'='*60}")
    print("  RESULT")
    print(f"{'='*60}")

    workspace = Path("workspace")
    for f in sorted(workspace.rglob("*")):
        if f.is_file() and not f.name.startswith("."):
            print(f"\n  {f.relative_to(workspace)}")

    print()


if __name__ == "__main__":
    main()
