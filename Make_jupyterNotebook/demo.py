#!/usr/bin/env python3
"""Demo script showcasing all features of the notebook annotator."""

import os
import sys
import json
from pathlib import Path

# Load env
env_file = Path(__file__).parent / "env.txt"
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value


def demo_basic_agent():
    """Run the basic agent pipeline."""
    print("[DEMO 1] Running LangGraph agent on practice notebook...")
    os.system("python agent.py --notebook practice_notebook.ipynb --output-dir output")
    print("✓ Agent complete. Check output/ directory.\n")


def demo_semantic_search():
    """Demonstrate semantic search."""
    print("[DEMO 2] Semantic search over knowledge graph...")
    try:
        from utils.semantic_search import query_graph_semantic

        results = query_graph_semantic(
            "data visualization and plotting",
            "output/knowledge_graph.json"
        )

        print(f"Query: '{results['query']}'")
        print("Top matches:")
        for match in results["matches"]:
            node = match["node"]
            score = match["score"]
            label = node.get("text") or node.get("source", "")[:50]
            print(f"  - {label} (score: {score:.3f})")
        print()
    except ImportError:
        print("! Skipping semantic search (openai not fully configured)")


def demo_variable_dependencies():
    """Demonstrate variable dependency analysis."""
    print("[DEMO 3] Analyzing variable dependencies between cells...")
    try:
        from utils.ast_analyzer import analyze_code_dependencies
        import nbformat

        with open("practice_notebook.ipynb", "r") as f:
            nb = nbformat.read(f, as_version=4)

        cells = [{"type": c.cell_type, "source": c.source} for c in nb.cells]
        deps = analyze_code_dependencies(cells)

        print("Cell dependency analysis:")
        for cell_idx in sorted([k for k in deps.keys() if isinstance(k, int)])[:5]:
            dep_info = deps[cell_idx]
            print(f"\n  Cell {cell_idx}:")
            print(f"    Assigns: {dep_info['assigns']}")
            print(f"    Uses: {dep_info['uses']}")
            if dep_info["depends_on"]:
                for dep in dep_info["depends_on"]:
                    print(f"      <- Cell {dep['cell_index']}: {dep['variables']}")
        print()
    except Exception as e:
        print(f"! Skipping variable analysis: {e}\n")


def demo_interactive_viz():
    """Generate interactive visualization."""
    print("[DEMO 4] Creating interactive HTML visualization...")
    try:
        from utils.interactive_viz import create_interactive_html_graph

        create_interactive_html_graph(
            "output/knowledge_graph.json",
            "output/knowledge_graph.gpickle",
            "output/graph_interactive.html"
        )
        print("✓ Open output/graph_interactive.html in a browser.\n")
    except ImportError:
        print("! Skipping interactive viz (pyvis not installed)\n")


def demo_quiz_generation():
    """Generate quiz questions."""
    print("[DEMO 5] Generating quiz questions from code cells...")
    try:
        from utils.quiz_generator import generate_quiz_from_graph
        import nbformat

        with open("practice_notebook.ipynb", "r") as f:
            nb = nbformat.read(f, as_version=4)

        cells = [{"type": c.cell_type, "source": c.source} for c in nb.cells]
        quiz = generate_quiz_from_graph(
            "output/knowledge_graph.gpickle",
            cells,
            "output/quiz.json"
        )

        print("Generated quiz questions:")
        for i, q in enumerate(quiz[:3], 1):
            print(f"\n  Q{i}: {q.get('question', 'N/A')}")
            print(f"      Answer: {q.get('answer', 'N/A')}")
        if len(quiz) > 3:
            print(f"  ... and {len(quiz) - 3} more questions")
        print()
    except Exception as e:
        print(f"! Skipping quiz generation: {e}\n")


def demo_graph_statistics():
    """Display graph statistics."""
    print("[DEMO 6] Knowledge graph statistics...")
    try:
        with open("output/knowledge_graph.json", "r") as f:
            graph = json.load(f)

        nodes = graph["nodes"]
        edges = graph["edges"]

        headings = [n for n in nodes if n["type"] == "HEADING"]
        code_cells = [n for n in nodes if n["type"] == "CODE_CELL"]

        belong_edges = [e for e in edges if e["type"] == "IS_BELONG_TO"]
        next_edges = [e for e in edges if e["type"] == "IS_NEXT_TO"]

        print(f"  Total nodes: {len(nodes)}")
        print(f"    - Headings: {len(headings)}")
        print(f"    - Code cells: {len(code_cells)}")
        print(f"  Total edges: {len(edges)}")
        print(f"    - IS_BELONG_TO: {len(belong_edges)}")
        print(f"    - IS_NEXT_TO: {len(next_edges)}")

        heading_levels = set(h["level"] for h in headings)
        print(f"  Heading levels used: {sorted(heading_levels)}")
        print()
    except Exception as e:
        print(f"! Error reading graph: {e}\n")


def demo_cytoscape_export():
    """Export to Cytoscape format."""
    print("[DEMO 7] Exporting to Cytoscape JSON...")
    try:
        from utils.interactive_viz import export_to_cytoscape

        export_to_cytoscape("output/knowledge_graph.json", "output/cytoscape.json")
        print("✓ Exported to output/cytoscape.json\n")
    except Exception as e:
        print(f"! Skipping Cytoscape export: {e}\n")


def main():
    """Run all demos."""
    print("=" * 60)
    print("LangGraph Notebook Annotator - Feature Demonstrations")
    print("=" * 60 + "\n")

    if not os.path.exists("practice_notebook.ipynb"):
        print("! practice_notebook.ipynb not found. Running basic agent first...")
        demo_basic_agent()
    elif not os.path.exists("output/knowledge_graph.json"):
        print("! Graph not found. Running basic agent first...")
        demo_basic_agent()

    # Run all demos
    demo_graph_statistics()
    demo_semantic_search()
    demo_variable_dependencies()
    demo_interactive_viz()
    demo_quiz_generation()
    demo_cytoscape_export()

    print("=" * 60)
    print("Demos complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
