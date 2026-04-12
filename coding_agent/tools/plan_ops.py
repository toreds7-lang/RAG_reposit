from tools.file_ops import write_file


def write_plan_md(plan_text: str, workspace_dir: str | None = None) -> str:
    return write_file("plan.md", plan_text, workspace_dir)
