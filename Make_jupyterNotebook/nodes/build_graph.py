import re
from typing import TypedDict


class NotebookState(TypedDict):
    notebook_path: str
    raw_cells: list
    annotated_cells: list
    knowledge_graph: dict
    output_notebook_path: str
    output_graph_path: str


def extract_heading_level_and_text(markdown_text: str) -> tuple:
    """Extract heading level (1, 2, 3...) and text from markdown."""
    match = re.match(r"^(#+)\s+(.+)$", markdown_text, re.MULTILINE)
    if match:
        level = len(match.group(1))
        text = match.group(2).strip()
        return level, text
    return None, None


def build_knowledge_graph_node(state: NotebookState) -> NotebookState:
    """Parse annotated cells to build knowledge graph with IS_BELONG_TO and IS_NEXT_TO edges."""
    annotated_cells = state["annotated_cells"]

    nodes = []
    edges = []
    heading_stack = []  # Stack of (level, node_id)
    prev_at_level = {}  # Previous node ID at each level
    node_counter = 0

    for cell in annotated_cells:
        if cell["type"] == "markdown":
            # Check if this is a heading
            first_line = cell["source"].split("\n")[0]
            level, text = extract_heading_level_and_text(first_line)

            if level is not None:
                node_id = f"heading_{node_counter}"
                node_counter += 1

                nodes.append({
                    "id": node_id,
                    "type": "HEADING",
                    "level": level,
                    "text": text,
                    "source": cell["source"]
                })

                # Pop stack entries with level >= current level
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()

                # Add IS_BELONG_TO edge to parent
                if heading_stack:
                    parent_id = heading_stack[-1][1]
                    edges.append({
                        "source": node_id,
                        "target": parent_id,
                        "type": "IS_BELONG_TO"
                    })

                # Add IS_NEXT_TO edge for sibling headings at same level
                if level in prev_at_level:
                    prev_id = prev_at_level[level]
                    edges.append({
                        "source": prev_id,
                        "target": node_id,
                        "type": "IS_NEXT_TO"
                    })

                prev_at_level[level] = node_id
                heading_stack.append((level, node_id))

        elif cell["type"] == "code":
            node_id = f"code_{node_counter}"
            node_counter += 1

            nodes.append({
                "id": node_id,
                "type": "CODE_CELL",
                "source": cell["source"][:200]  # Truncate for readability
            })

            # Add IS_BELONG_TO edge to current heading
            if heading_stack:
                parent_id = heading_stack[-1][1]
                edges.append({
                    "source": node_id,
                    "target": parent_id,
                    "type": "IS_BELONG_TO"
                })

    state["knowledge_graph"] = {
        "nodes": nodes,
        "edges": edges
    }

    return state
