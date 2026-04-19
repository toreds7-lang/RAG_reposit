import nbformat
import os
from typing import TypedDict


class NotebookState(TypedDict):
    notebook_path: str
    raw_cells: list
    annotated_cells: list
    knowledge_graph: dict
    output_notebook_path: str
    output_graph_path: str


def annotate_notebook_node(state: NotebookState) -> NotebookState:
    """Insert markdown cells into notebook and save."""
    annotated_cells = state["annotated_cells"]
    output_path = state.get("output_notebook_path", "output/annotated_notebook.ipynb")

    # Create output directory if needed
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Create new notebook
    notebook = nbformat.v4.new_notebook()

    for cell_data in annotated_cells:
        if cell_data["type"] == "markdown":
            cell = nbformat.v4.new_markdown_cell(cell_data["source"])
        else:  # code
            cell = nbformat.v4.new_code_cell(cell_data["source"])

        notebook.cells.append(cell)

    # Save notebook
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(notebook, f)

    print(f"Annotated notebook saved to {output_path}")
    state["output_notebook_path"] = output_path
    return state
