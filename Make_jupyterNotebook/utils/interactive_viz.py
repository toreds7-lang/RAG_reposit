import json
import os
from pyvis.network import Network
import networkx as nx


def create_interactive_html_graph(json_path: str, pickle_path: str, output_path: str):
    """Create interactive HTML visualization using pyvis."""
    # Load graph
    with open(pickle_path, "rb") as f:
        import pickle
        G = pickle.load(f)

    # Load data for labels
    with open(json_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    node_map = {n["id"]: n for n in graph_data["nodes"]}

    # Create pyvis network
    net = Network(directed=True, height="750px", width="100%")
    net.from_nx(G)

    # Update node styling
    for node in net.nodes:
        node_id = node["id"]
        node_info = node_map.get(node_id, {})
        node_type = node_info.get("type", "UNKNOWN")

        if node_type == "HEADING":
            level = node_info.get("level", 1)
            text = node_info.get("text", "Heading")[:30]
            size = 40 - (level - 1) * 10
            color = "#87CEEB"  # Light blue
            node["title"] = text
            node["label"] = f"{text} (H{level})"
            node["size"] = max(size, 20)
            node["color"] = color
        else:  # CODE_CELL
            source = node_info.get("source", "")[:50]
            node["title"] = source
            node["label"] = "Code"
            node["size"] = 25
            node["color"] = "#90EE90"  # Light green

    # Update edge styling
    for edge in net.edges:
        relation = edge.get("relation", "UNKNOWN")
        if relation == "IS_BELONG_TO":
            edge["color"] = "#FF6B6B"  # Red
            edge["title"] = "IS_BELONG_TO"
        elif relation == "IS_NEXT_TO":
            edge["color"] = "#4169E1"  # Blue
            edge["dashes"] = True
            edge["title"] = "IS_NEXT_TO"

    # Configure physics and save
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    net.write_html(output_path)
    print(f"Interactive graph saved to {output_path}")


def export_to_cytoscape(json_path: str, output_path: str):
    """Export graph in Cytoscape JSON format for other tools."""
    with open(json_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    cytoscape_format = {
        "elements": []
    }

    # Add nodes
    for node in graph_data["nodes"]:
        cytoscape_format["elements"].append({
            "data": {
                "id": node["id"],
                "label": node.get("text") or node.get("source", "")[:50],
                "type": node["type"]
            }
        })

    # Add edges
    for edge in graph_data["edges"]:
        cytoscape_format["elements"].append({
            "data": {
                "id": f"{edge['source']}_to_{edge['target']}",
                "source": edge["source"],
                "target": edge["target"],
                "relation": edge["type"]
            }
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cytoscape_format, f, indent=2)
    print(f"Cytoscape graph saved to {output_path}")
