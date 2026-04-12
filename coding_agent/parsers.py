import re


def extract_code_block(text: str) -> str:
    """Extract code from ``` ... ``` blocks with any language tag."""
    match = re.search(r"```\w*\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def extract_filename(text: str) -> str:
    """Extract filename from FILENAME: xxx.py pattern."""
    match = re.search(r"FILENAME:\s*(\S+\.\w+)", text)
    if match:
        return match.group(1)
    return "solution.py"
