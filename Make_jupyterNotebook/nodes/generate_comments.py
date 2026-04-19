import json
import os
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


class NotebookState(TypedDict):
    notebook_path: str
    raw_cells: list
    annotated_cells: list
    knowledge_graph: dict
    output_notebook_path: str
    output_graph_path: str


def generate_comments_node(state: NotebookState) -> NotebookState:
    """Generate hierarchical markdown comments for code cells using OpenAI LLM."""
    raw_cells = state["raw_cells"]

    # Extract only code cells with their indices
    code_cell_info = []
    for cell in raw_cells:
        if cell["type"] == "code":
            code_cell_info.append({
                "index": cell["index"],
                "source": cell["source"][:300]  # Truncate for token limit
            })

    if not code_cell_info:
        return state

    # Format cells for LLM
    cells_text = "\n\n".join([
        f"Cell {i}: {cell['source']}" for i, cell in enumerate(code_cell_info)
    ])

    # Create LLM instance
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")

    llm = ChatOpenAI(
        api_key=api_key,
        model="gpt-4o-mini",
        temperature=0.7,
    )

    # System and user prompts
    system_prompt = """You are an expert educator writing markdown comments for Jupyter notebooks.
Given a sequence of code cells, generate hierarchical markdown headers (#, ##, ###) that explain
what each section does. Use # for major topics, ## for subtopics, ### for specific steps.

Return a JSON array where each element is a markdown string with headers, or null if no comment is needed.
The array should have the same length as the number of code cells provided."""

    user_prompt = f"""Here are the code cells in order:

{cells_text}

Generate educational markdown comments (using #, ##, ###) for these cells.
Return a JSON array with {len(code_cell_info)} elements (one per cell):

Example output format:
["# Data Loading\\n## Reading CSV Files", "## Data Exploration", null, "# Visualization\\n## Creating Plots"]

Respond ONLY with valid JSON array. Do not include markdown code blocks."""

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        response = llm.invoke(messages)
        response_text = response.content.strip()

        # Parse JSON response
        comments = json.loads(response_text)
        if not isinstance(comments, list):
            raise ValueError("Response is not a JSON array")

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: Could not parse LLM response. Using default structure. Error: {e}")
        # Fallback: create simple structure
        comments = ["# Section"] + [None] * (len(code_cell_info) - 1)

    # Inject markdown cells into annotated_cells
    annotated_cells = state["annotated_cells"].copy()
    offset = 0

    for comment_idx, comment in enumerate(comments):
        if comment is None:
            continue

        # Find the corresponding code cell in annotated_cells
        code_cell_count = 0
        for cell_idx, cell in enumerate(annotated_cells):
            if cell["type"] == "code":
                if code_cell_count == comment_idx:
                    # Insert a markdown cell before this code cell
                    new_markdown_cell = {
                        "type": "markdown",
                        "source": comment,
                        "metadata": {}
                    }
                    annotated_cells.insert(cell_idx + offset, new_markdown_cell)
                    offset += 1
                    break
                code_cell_count += 1

    state["annotated_cells"] = annotated_cells
    return state
