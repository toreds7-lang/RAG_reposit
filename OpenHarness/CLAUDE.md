# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This repository is in early initialization. No application code exists yet.

## Environment Configuration

The project uses a `.env` file for configuration. Key variables:

- `OPENAI_API_KEY` — OpenAI API key for LLM calls
- `LLM_MODEL` — Target model (default: `gpt-4o`)
- `LLM_BASE_URL` — Override base URL for LLM API (empty = OpenAI default)
- `EMBEDDING_MODEL` — Embedding model (default: `text-embedding-ada-002`)
- `EMBEDDING_BASE_URL` — Override base URL for embedding API

The `env.txt` file is a duplicate of `.env` — keep them in sync or remove the redundancy.

**Security note:** Never commit `.env` or `env.txt` to version control. Add both to `.gitignore`.
