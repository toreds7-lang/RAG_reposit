"""
RAG retrieval + GPT-4o chat logic.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import openai

import config

SYSTEM_PROMPT = (
    'You are an expert assistant on the paper "Attention Is All You Need" '
    "(Vaswani et al., 2017). Answer questions using the retrieved context. "
    "Be precise and cite page numbers when relevant. "
    "If the user has selected a specific element from the PDF, treat it as primary context."
)


# ---------------------------------------------------------------------------
# OpenAI client (lazy singleton)
# ---------------------------------------------------------------------------

_client: Optional[openai.OpenAI] = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        kwargs: dict = {"api_key": config.OPENAI_API_KEY}
        if config.LLM_BASE_URL:
            kwargs["base_url"] = config.LLM_BASE_URL
        _client = openai.OpenAI(**kwargs)
    return _client


def _get_embed_client() -> openai.OpenAI:
    """Separate client for embeddings (may use a different base_url)."""
    kwargs: dict = {"api_key": config.OPENAI_API_KEY}
    if config.EMBEDDING_BASE_URL:
        kwargs["base_url"] = config.EMBEDDING_BASE_URL
    return openai.OpenAI(**kwargs)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def embed_query(text: str) -> np.ndarray:
    """Return a (1536,) float32 embedding for `text`."""
    client = _get_embed_client()
    response = client.embeddings.create(input=[text], model=config.EMBEDDING_MODEL)
    return np.array(response.data[0].embedding, dtype=np.float32)


def retrieve(
    query: str,
    index,
    elements: list[dict],
    top_k: int = config.FAISS_TOP_K,
) -> list[dict]:
    """FAISS nearest-neighbour search; returns top_k matching elements."""
    vec = embed_query(query).reshape(1, -1)
    _distances, indices = index.search(vec, top_k)
    results = []
    for idx in indices[0]:
        if 0 <= idx < len(elements):
            results.append(elements[idx])
    return results


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_user_message(
    question: str,
    retrieved: list[dict],
    selected_elements: list[dict],
) -> str:
    """Build the user-turn message that injects RAG context."""
    context_parts: list[str] = []

    total_selected = len(selected_elements)
    for i, elem in enumerate(selected_elements, start=1):
        etype = elem["element_type"].upper()
        page = elem["page_no"]
        content = elem["text"]
        header = (
            f"[SELECTED {etype} — Page {page}]"
            if total_selected == 1
            else f"[SELECTED {i}/{total_selected} — {etype} — Page {page}]"
        )
        context_parts.append(f"{header}\n{content}")

    for i, elem in enumerate(retrieved):
        page = elem["page_no"]
        etype = elem["element_type"]
        content = elem["text"]
        context_parts.append(f"[RETRIEVED CHUNK {i + 1} — {etype}, Page {page}]\n{content}")

    context_block = "\n\n---\n\n".join(context_parts)
    return f"Context from the paper:\n\n{context_block}\n\n---\n\nQuestion: {question}"


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def chat(
    question: str,
    retrieved: list[dict],
    selected_elements: list[dict],
    history: list[dict],
) -> str:
    """
    Call GPT-4o with the full conversation history + injected RAG context.
    Returns the assistant's reply string.
    """
    client = _get_client()

    user_msg = build_user_message(question, retrieved, selected_elements)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # Inject prior turns (skip the most-recent user msg; we'll add it with context)
    messages.extend(history)
    messages.append({"role": "user", "content": user_msg})

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
    )
    return response.choices[0].message.content or ""
