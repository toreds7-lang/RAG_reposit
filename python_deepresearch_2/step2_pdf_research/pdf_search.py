"""
Hybrid retrieval over PDF chunks: BM25 + OpenAI vector embeddings with
Reciprocal Rank Fusion (RRF).

Cached embeddings are keyed by sha256(pdf_bytes + chunk_size + overlap) to invalidate
correctly when the PDF content changes (even at the same path). BM25 is rebuilt
in-memory from chunk texts on every run (fast; no API cost).

Standalone smoke test:
    python -m step2_pdf_research.pdf_search --pdf 1706.03762v7.pdf --query "training procedures"
"""

import argparse
import hashlib
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Set

import numpy as np
from rank_bm25 import BM25Okapi

from step2_pdf_research.pdf_ingestion import Chunk, ingest_pdf

logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
DEFAULT_BM25_WEIGHT = 0.4
DEFAULT_VEC_WEIGHT = 0.6
RRF_K = 60

_BM25_TOKEN_RE = re.compile(r"[^a-z0-9_]+")


@dataclass
class HybridIndex:
    chunks: List[Chunk]
    bm25: BM25Okapi
    embeddings: np.ndarray       # shape (N, EMBED_DIM), L2-normalized, float32
    cache_path: str


def tokenize_for_bm25(text: str) -> List[str]:
    return [t for t in _BM25_TOKEN_RE.split(text.lower()) if len(t) >= 2]


def _cache_key(pdf_path: str, chunk_size: int, overlap: int) -> str:
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    h.update(f"|cs={chunk_size}|ov={overlap}|m={EMBED_MODEL}".encode())
    return h.hexdigest()[:16]


def embed_texts(texts: List[str], client, batch_size: int = 100) -> np.ndarray:
    """Batch-embed texts. Returns (N, EMBED_DIM) float32 array."""
    all_vecs: List[np.ndarray] = []
    n_batches = (len(texts) + batch_size - 1) // batch_size
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        t0 = time.time()
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
        all_vecs.append(vecs)
        logger.info(
            "embed_texts | batch %d/%d | n=%d | elapsed=%.1fs",
            i // batch_size + 1, n_batches, len(batch), time.time() - t0,
        )
    return np.vstack(all_vecs) if all_vecs else np.zeros((0, EMBED_DIM), dtype=np.float32)


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (matrix / norms).astype(np.float32)


def cosine_similarity_batch(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Assumes both inputs are L2-normalized → cosine sim = dot product."""
    return matrix @ query_vec


def build_index(
    chunks: List[Chunk],
    client,
    pdf_path: str,
    chunk_size: int,
    overlap: int,
    cache_dir: str = "output",
) -> HybridIndex:
    os.makedirs(cache_dir, exist_ok=True)
    key = _cache_key(pdf_path, chunk_size, overlap)
    cache_path = os.path.join(cache_dir, f"pdf_index_{key}.npz")

    texts = [c.text for c in chunks]

    if os.path.exists(cache_path):
        logger.info("build_index | CACHE HIT | path=%s", cache_path)
        data = np.load(cache_path)
        embeddings = data["embeddings"].astype(np.float32)
        if embeddings.shape[0] != len(chunks):
            logger.warning(
                "Cache chunk count (%d) != current (%d) — rebuilding",
                embeddings.shape[0], len(chunks),
            )
            embeddings = None  # fall through
        else:
            bm25 = BM25Okapi([tokenize_for_bm25(t) for t in texts])
            return HybridIndex(chunks=chunks, bm25=bm25, embeddings=embeddings, cache_path=cache_path)

    logger.info("build_index | CACHE MISS | embedding %d chunks", len(chunks))
    raw = embed_texts(texts, client)
    embeddings = _l2_normalize(raw)
    np.savez(cache_path, embeddings=embeddings)
    logger.info("build_index | saved cache | path=%s | shape=%s", cache_path, embeddings.shape)

    bm25 = BM25Okapi([tokenize_for_bm25(t) for t in texts])
    return HybridIndex(chunks=chunks, bm25=bm25, embeddings=embeddings, cache_path=cache_path)


def reciprocal_rank_fusion(
    bm25_ranked: List[int],
    vec_ranked: List[int],
    k: int = RRF_K,
    bm25_weight: float = DEFAULT_BM25_WEIGHT,
    vec_weight: float = DEFAULT_VEC_WEIGHT,
) -> List[int]:
    """Fuse two ranked id-lists into a single ranking by weighted RRF."""
    scores: dict[int, float] = {}
    for rank, cid in enumerate(bm25_ranked):
        scores[cid] = scores.get(cid, 0.0) + bm25_weight / (k + rank)
    for rank, cid in enumerate(vec_ranked):
        scores[cid] = scores.get(cid, 0.0) + vec_weight / (k + rank)
    return sorted(scores.keys(), key=lambda i: scores[i], reverse=True)


def search_hybrid(
    query: str,
    index: HybridIndex,
    client,
    top_k: int = 8,
    exclude_chunk_ids: Optional[Set[int]] = None,
) -> List[Chunk]:
    """Embed query, rank via BM25 and cosine, fuse with RRF, return top_k Chunks."""
    exclude = exclude_chunk_ids or set()
    n = len(index.chunks)
    if n == 0:
        return []

    # Vector ranking (query embedding + cosine sim over normalized doc matrix)
    q_resp = client.embeddings.create(model=EMBED_MODEL, input=[query])
    q_vec = np.array(q_resp.data[0].embedding, dtype=np.float32)
    q_vec = q_vec / (np.linalg.norm(q_vec) or 1.0)
    vec_scores = cosine_similarity_batch(q_vec, index.embeddings)
    vec_order = np.argsort(-vec_scores).tolist()
    vec_ranked = [i for i in vec_order if i not in exclude]

    # BM25 ranking
    bm25_scores = index.bm25.get_scores(tokenize_for_bm25(query))
    bm25_order = np.argsort(-bm25_scores).tolist()
    bm25_ranked = [i for i in bm25_order if i not in exclude]

    fused = reciprocal_rank_fusion(bm25_ranked, vec_ranked)
    top_ids = fused[:top_k]
    logger.info(
        "search_hybrid | query='%.60s' | excluded=%d | bm25_top3=%s | vec_top3=%s | fused_top3=%s",
        query, len(exclude), bm25_ranked[:3], vec_ranked[:3], top_ids[:3],
    )
    return [index.chunks[i] for i in top_ids]


def _smoke_test():
    from dotenv import load_dotenv
    from openai import OpenAI
    from utils import setup_logging

    load_dotenv()
    setup_logging()

    parser = argparse.ArgumentParser(description="Smoke test: retrieve top chunks for a query.")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--overlap", type=int, default=None)
    args = parser.parse_args()

    client = OpenAI()
    chunks, cs, ov = ingest_pdf(args.pdf, chunk_size=args.chunk_size, overlap=args.overlap)
    print(f"Ingested {len(chunks)} chunks from {args.pdf} (chunk_size={cs}, overlap={ov})")

    index = build_index(chunks, client, args.pdf, chunk_size=cs, overlap=ov)
    results = search_hybrid(args.query, index, client, top_k=args.top_k)
    print(f"\nTop {len(results)} chunks for query: '{args.query}'\n")
    for rank, c in enumerate(results, 1):
        preview = c.text[:120].replace("\n", " ")
        print(f"[{rank}] chunk_id={c.chunk_id} | p{c.page_start}-{c.page_end} | "
              f"section='{c.section_hint}' | tokens={c.token_count}")
        print(f"    {preview}...")
        print()


if __name__ == "__main__":
    _smoke_test()
