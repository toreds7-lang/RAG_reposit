import json
import os
import pickle
from pathlib import Path
from openai import OpenAI
import networkx as nx


def load_graph(graph_path: str):
    """Load knowledge graph from pickle file."""
    with open(graph_path, "rb") as f:
        return pickle.load(f)


def load_graph_data(json_path: str) -> dict:
    """Load knowledge graph JSON."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def query_graph_semantic(query: str, json_path: str, api_key: str = None) -> dict:
    """Search knowledge graph using semantic similarity."""
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")

    graph_data = load_graph_data(json_path)
    client = OpenAI(api_key=api_key)

    # Get embedding for query
    query_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )
    query_embedding = query_response.data[0].embedding

    # Compute embeddings for all nodes (cached in memory for efficiency)
    node_embeddings = {}
    for node in graph_data["nodes"]:
        node_text = node.get("text") or node.get("source", "")[:100]
        if node_text:
            emb_response = client.embeddings.create(
                model="text-embedding-3-small",
                input=node_text
            )
            node_embeddings[node["id"]] = emb_response.data[0].embedding

    # Compute cosine similarity
    import numpy as np

    def cosine_sim(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    similarities = {}
    for node_id, embedding in node_embeddings.items():
        sim = cosine_sim(query_embedding, embedding)
        similarities[node_id] = sim

    # Return top matches
    top_matches = sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:5]
    matched_nodes = [
        next((n for n in graph_data["nodes"] if n["id"] == node_id), {})
        for node_id, score in top_matches
    ]

    return {
        "query": query,
        "matches": [
            {"node": node, "score": float(score)}
            for node, (node_id, score) in zip(matched_nodes, top_matches)
        ]
    }


def get_node_context(node_id: str, json_path: str, graph_path: str) -> dict:
    """Get context for a node (parents, children, siblings)."""
    graph_data = load_graph_data(json_path)
    G = load_graph(graph_path)

    node = next((n for n in graph_data["nodes"] if n["id"] == node_id), None)
    if not node:
        return {"error": "Node not found"}

    # Find parents (targets of IS_BELONG_TO edges)
    parents = [
        edge["target"]
        for edge in graph_data["edges"]
        if edge["source"] == node_id and edge["type"] == "IS_BELONG_TO"
    ]

    # Find children (sources of IS_BELONG_TO edges to this node)
    children = [
        edge["source"]
        for edge in graph_data["edges"]
        if edge["target"] == node_id and edge["type"] == "IS_BELONG_TO"
    ]

    # Find siblings (IS_NEXT_TO edges)
    siblings = []
    for edge in graph_data["edges"]:
        if edge["source"] == node_id and edge["type"] == "IS_NEXT_TO":
            siblings.append(edge["target"])
        elif edge["target"] == node_id and edge["type"] == "IS_NEXT_TO":
            siblings.append(edge["source"])

    return {
        "node": node,
        "parents": [next((n for n in graph_data["nodes"] if n["id"] == p), {}) for p in parents],
        "children": [next((n for n in graph_data["nodes"] if n["id"] == c), {}) for c in children],
        "siblings": [next((n for n in graph_data["nodes"] if n["id"] == s), {}) for s in siblings]
    }
