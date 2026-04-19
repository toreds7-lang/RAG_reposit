import nbformat
from typing import TypedDict


class NotebookState(TypedDict):
    notebook_path: str
    raw_cells: list
    annotated_cells: list
    knowledge_graph: dict
    output_notebook_path: str
    output_graph_path: str


def read_notebook_node(state: NotebookState) -> NotebookState:
    """Parse Jupyter notebook and extract cells."""
    notebook_path = state["notebook_path"]

    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook = nbformat.read(f, as_version=4)

    raw_cells = []
    for i, cell in enumerate(notebook.cells):
        raw_cells.append({
            "index": i,
            "type": cell.cell_type,
            "source": cell.source,
            "metadata": cell.get("metadata", {})
        })

    state["raw_cells"] = raw_cells
    state["annotated_cells"] = [cell.copy() for cell in raw_cells]

    return state
