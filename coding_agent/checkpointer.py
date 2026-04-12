import uuid
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer():
    """Return a checkpointer for graph state persistence.

    Uses MemorySaver for now. Can be swapped to SqliteSaver later:
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver.from_conn_string("checkpoints.db")
    """
    return MemorySaver()


def get_thread_config(thread_id: str | None = None) -> dict:
    """Create a config dict with thread_id for checkpointer."""
    if thread_id is None:
        thread_id = str(uuid.uuid4())[:8]
    return {"configurable": {"thread_id": thread_id}}
