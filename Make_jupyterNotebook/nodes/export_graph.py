import json
import os
import networkx as nx
import matplotlib.pyplot as plt
from typing import TypedDict


class NotebookState(TypedDict):
    notebook_path: str
    raw_cells: list
    annotated_cells: list
    knowledge_graph: dict
    output_notebook_path: str
    output_graph_path: str


def export_graph_node(state: NotebookState) -> NotebookState:
    """Export knowledge graph as JSON and NetworkX visualization."""
    kg = state["knowledge_graph"]
    output_dir = state.get("output_graph_path", "output") or "output"

    os.makedirs(output_dir, exist_ok=True)

    # Save JSON
    json_path = os.path.join(output_dir, "knowledge_graph.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(kg, f, indent=2)

    print(f"Knowledge graph JSON saved to {json_path}")

    # Build NetworkX graph
    G = nx.DiGraph()

    # Add nodes with labels
    for node in kg["nodes"]:
        label = node.get("text", node.get("source", "")[:30])
        color = "lightblue" if node["type"] == "HEADING" else "lightgreen"
        G.add_node(node["id"], label=label, type=node["type"], color=color)

    # Add edges
    for edge in kg["edges"]:
        G.add_edge(edge["source"], edge["target"], relation=edge["type"])

    # Create visualization
    plt.figure(figsize=(14, 10))
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # Draw nodes by type
    heading_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "HEADING"]
    code_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "CODE_CELL"]

    nx.draw_networkx_nodes(G, pos, nodelist=heading_nodes, node_color="lightblue",
                          node_size=800, label="Heading")
    nx.draw_networkx_nodes(G, pos, nodelist=code_nodes, node_color="lightgreen",
                          node_size=600, label="Code Cell")

    # Draw edges with labels
    edges_belong = [(u, v) for u, v, d in G.edges(data=True) if d.get("relation") == "IS_BELONG_TO"]
    edges_next = [(u, v) for u, v, d in G.edges(data=True) if d.get("relation") == "IS_NEXT_TO"]

    nx.draw_networkx_edges(G, pos, edgelist=edges_belong, edge_color="red",
                          arrows=True, arrowsize=15, width=2, label="IS_BELONG_TO")
    nx.draw_networkx_edges(G, pos, edgelist=edges_next, edge_color="blue",
                          arrows=True, arrowsize=15, width=2, style="dashed", label="IS_NEXT_TO")

    # Draw labels
    labels = {n: G.nodes[n].get("label", n)[:15] for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=8)

    plt.title("Jupyter Notebook Knowledge Graph")
    plt.legend(scatterpoints=1, loc="upper left")
    plt.axis("off")

    png_path = os.path.join(output_dir, "knowledge_graph.png")
    plt.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Graph visualization saved to {png_path}")

    # Save NetworkX graph
    import pickle
    gpickle_path = os.path.join(output_dir, "knowledge_graph.gpickle")
    with open(gpickle_path, "wb") as f:
        pickle.dump(G, f)
    print(f"NetworkX graph saved to {gpickle_path}")

    state["output_graph_path"] = output_dir
    return state
