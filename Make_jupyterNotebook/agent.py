import os
import argparse
from pathlib import Path
from langgraph.graph import StateGraph, START, END
from nodes.read_notebook import NotebookState, read_notebook_node
from nodes.generate_comments import generate_comments_node
from nodes.annotate_notebook import annotate_notebook_node
from nodes.build_graph import build_knowledge_graph_node
from nodes.export_graph import export_graph_node


def load_env():
    """Load environment variables from env.txt."""
    env_file = Path(__file__).parent / "env.txt"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value


def create_agent():
    """Create and return the LangGraph workflow."""
    builder = StateGraph(NotebookState)

    # Add nodes
    builder.add_node("read_notebook", read_notebook_node)
    builder.add_node("generate_comments", generate_comments_node)
    builder.add_node("annotate_notebook", annotate_notebook_node)
    builder.add_node("build_knowledge_graph", build_knowledge_graph_node)
    builder.add_node("export_graph", export_graph_node)

    # Add edges
    builder.add_edge(START, "read_notebook")
    builder.add_edge("read_notebook", "generate_comments")
    builder.add_edge("generate_comments", "annotate_notebook")
    builder.add_edge("annotate_notebook", "build_knowledge_graph")
    builder.add_edge("build_knowledge_graph", "export_graph")
    builder.add_edge("export_graph", END)

    return builder.compile()


def main():
    parser = argparse.ArgumentParser(description="Process Jupyter notebook with LangGraph agent")
    parser.add_argument("--notebook", type=str, default="practice_notebook.ipynb",
                       help="Path to input notebook")
    parser.add_argument("--output-dir", type=str, default="output",
                       help="Output directory for annotated notebook and graph")

    args = parser.parse_args()

    # Load environment
    load_env()

    # Verify API key
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not found in env.txt")

    # Create agent
    agent = create_agent()

    # Initial state
    initial_state: NotebookState = {
        "notebook_path": args.notebook,
        "raw_cells": [],
        "annotated_cells": [],
        "knowledge_graph": {"nodes": [], "edges": []},
        "output_notebook_path": os.path.join(args.output_dir, "annotated_notebook.ipynb"),
        "output_graph_path": args.output_dir,
    }

    print(f"Processing notebook: {args.notebook}")
    print(f"Output directory: {args.output_dir}\n")

    # Run agent
    final_state = agent.invoke(initial_state)

    print("\n[OK] Notebook processing complete!")
    print(f"  - Annotated notebook: {final_state['output_notebook_path']}")
    print(f"  - Knowledge graph JSON: {os.path.join(final_state['output_graph_path'], 'knowledge_graph.json')}")
    print(f"  - Visualization PNG: {os.path.join(final_state['output_graph_path'], 'knowledge_graph.png')}")
    print(f"\nGraph Summary:")
    print(f"  - Total nodes: {len(final_state['knowledge_graph']['nodes'])}")
    print(f"  - Total edges: {len(final_state['knowledge_graph']['edges'])}")


if __name__ == "__main__":
    main()
