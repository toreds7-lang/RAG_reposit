# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python implementation of a Deep Research agent — an AI pipeline that generates clarifying questions, conducts recursive web searches, and synthesizes findings into a markdown report. Based on [dzhng/deep-research](https://github.com/dzhng/deep-research).

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Run the main research pipeline
python main.py

# Test LLM and Firecrawl API connectivity
python test.py
```

Requires a `.env` file with:
```
OPENAI_API_KEY=...
FIRECRAWL_API_KEY=...
```

## Architecture

Three-stage pipeline orchestrated by `main.py`:

1. **Feedback** (`step1_feedback/feedback.py`) — Uses `gpt-4o-mini` to generate 1–3 clarifying questions about the research topic. Returns structured JSON via Pydantic schema.

2. **Research** (`step2_research/research.py`) — Recursive web research engine. For each iteration: generates SERP queries → calls Firecrawl to search/scrape → extracts learnings and follow-up questions → recurses. Controlled by `breadth` (parallel searches per level) and `depth` (recursion levels). Recommended: breadth=2, depth=2.

3. **Reporting** (`step3_reporting/reporting.py`) — Uses `o1-mini` to synthesize all learnings into a markdown report saved to `output/output.md`.

### Shared Utilities (`utils.py`)

- `system_prompt()` — Expert researcher persona with current timestamp
- `llm_call()` — Synchronous text generation
- `JSON_llm(prompt, schema)` — Structured output using `openai.beta.chat.completions.parse()` with a Pydantic model

### Key Constraints

- Firecrawl free tier is rate-limited to **5 requests/min** — high breadth/depth values will cause delays or failures
- `o1-mini` does **not** support structured output — use `llm_call()` for the reporting stage, not `JSON_llm()`
- Models that support structured output (for `JSON_llm()`): `gpt-4o`, `gpt-4o-mini`
