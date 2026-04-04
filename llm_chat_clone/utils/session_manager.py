import uuid
from datetime import datetime
import streamlit as st


def init_sessions() -> None:
    """Initialize session state on first app load."""
    if "sessions" not in st.session_state:
        st.session_state["sessions"] = {}
    if "active_session_id" not in st.session_state:
        create_new_session()
    if "is_streaming" not in st.session_state:
        st.session_state["is_streaming"] = False
    if "stop_requested" not in st.session_state:
        st.session_state["stop_requested"] = False
    if "pending_input" not in st.session_state:
        st.session_state["pending_input"] = None


def create_new_session() -> str:
    """Create a new chat session and activate it."""
    sid = str(uuid.uuid4())[:8]
    session_num = len(st.session_state.get("sessions", {})) + 1
    st.session_state["sessions"][sid] = {
        "name": f"Session {session_num}",
        "created_at": datetime.now().strftime("%H:%M"),
        "messages": [],
        "vectorstore": None,
        "pdf_names": [],
    }
    st.session_state["active_session_id"] = sid
    return sid


def get_active_session() -> dict:
    """Return the currently active session dict."""
    sid = st.session_state["active_session_id"]
    return st.session_state["sessions"][sid]


def add_message(role: str, content: str) -> None:
    """Append a message to the active session."""
    get_active_session()["messages"].append({"role": role, "content": content})


def switch_session(sid: str) -> None:
    """Switch to a different session."""
    st.session_state["active_session_id"] = sid
    # Reset streaming state when switching sessions
    st.session_state["is_streaming"] = False
    st.session_state["stop_requested"] = False
    st.session_state["pending_input"] = None
