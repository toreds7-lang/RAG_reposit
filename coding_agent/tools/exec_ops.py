import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent / "workspace"

DANGEROUS_PATTERNS = [
    "rm -rf", "rm -r /", "mkfs", "dd if=",
    "chmod -R 777 /", "curl | sh", "wget | sh",
    "format", "del /s /q",
]


def run_command(
    command: str,
    cwd: str | None = None,
    timeout: int = 30,
) -> tuple[str, str, int]:
    work_dir = cwd or str(WORKSPACE)

    for pattern in DANGEROUS_PATTERNS:
        if pattern in command:
            return ("", f"BLOCKED: dangerous command pattern '{pattern}'", 1)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
        )
        return (result.stdout, result.stderr, result.returncode)
    except subprocess.TimeoutExpired:
        return ("", f"TIMEOUT: command exceeded {timeout}s", 1)
    except Exception as e:
        return ("", f"EXEC ERROR: {str(e)}", 1)
