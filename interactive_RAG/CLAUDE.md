# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

This is an interactive RAG (Retrieval-Augmented Generation) system. The reference document is `1706.03762v7.pdf` (the "Attention is All You Need" transformer paper, arXiv).

## Environment Configuration

Environment variables are stored in `env.txt` (do **not** commit this file). Copy them to `.env` before running:

```
OPENAI_API_KEY=...
LLM_MODEL=gpt-4o
LLM_BASE_URL=          # leave empty to use OpenAI default
EMBEDDING_BASE_URL=    # leave empty to use OpenAI default
EMBEDDING_MODEL=text-embedding-ada-002
```

## Tech Stack (Planned)

- LLM: OpenAI GPT-4o
- Embeddings: OpenAI `text-embedding-ada-002`
- Document: PDF ingestion via the transformer paper as a knowledge base
