from pathlib import Path

WORKSPACE = Path(__file__).parent.parent / "workspace"


def write_file(filename: str, content: str, workspace_dir: str | None = None) -> str:
    base = Path(workspace_dir) if workspace_dir else WORKSPACE
    path = base / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {filename}"


def read_file(filename: str, workspace_dir: str | None = None) -> str:
    base = Path(workspace_dir) if workspace_dir else WORKSPACE
    path = base / filename
    if not path.exists():
        return f"ERROR: {filename} does not exist"
    return path.read_text(encoding="utf-8")


def apply_patch(current_content: str, old_str: str, new_str: str) -> str:
    if old_str not in current_content:
        raise ValueError(
            f"old_str not found in file. Cannot patch.\n"
            f"Searched for: {repr(old_str[:100])}"
        )
    return current_content.replace(old_str, new_str, 1)


def list_files(workspace_dir: str | None = None) -> list[str]:
    base = Path(workspace_dir) if workspace_dir else WORKSPACE
    if not base.exists():
        return []
    return [str(f.relative_to(base)) for f in base.rglob("*") if f.is_file()]
