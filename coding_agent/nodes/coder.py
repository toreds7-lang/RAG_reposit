"""Coder router — dispatches to backend_coder or frontend_coder based on goal keywords."""

FRONTEND_KEYWORDS = [
    "frontend", "html", "css", "react", "ui",
    "웹페이지", "화면", "javascript", "web page",
]


def route_to_coder(state: dict) -> str:
    goal_lower = state.get("goal", "").lower()
    if any(kw in goal_lower for kw in FRONTEND_KEYWORDS):
        return "frontend_coder"
    return "backend_coder"
