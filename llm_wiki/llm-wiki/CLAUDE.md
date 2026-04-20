# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

An Obsidian vault used as a personal knowledge base, following Andrej Karpathy's "LLM Wiki" pattern. Current scope: planning education about agent 

The human curates sources, asks questions, and guides analysis. Claude reads sources, maintains the wiki, and answers questions from it.

## Layout

- `raw/` — source documents. **Immutable.** Never modify anything here.
- `wiki/` — markdown pages Claude maintains.
- `wiki/index.md` — table of contents for the whole wiki (created on first ingest).
- `wiki/log.md` — append-only record of every operation (created on first ingest).
- `templates/` — page templates (currently empty).

## Ingest workflow

When the user drops a new source into `raw/` and asks you to ingest it:

1. Read the full source document.
2. Discuss key takeaways with the user before writing anything.
3. Create a summary page in `wiki/` named after the source.
4. Create or update concept pages for each major idea or entity.
5. Add `[[wiki-links]]` between related pages.
6. Update `wiki/index.md` with the new pages and one-line descriptions.
7. Append an entry to `wiki/log.md` with the date, source name, and what changed.

A single source may touch 10–15 wiki pages. That is normal.

## Page format

Every wiki page follows this structure:

```markdown
# Page Title

**Summary**: One to two sentences describing this page.

**Sources**: List of raw source files this page draws from.

**Last updated**: Date of most recent update.

---

Main content. Clear headings, short paragraphs.

Link to related concepts using [[wiki-links]] throughout the text.

## Related pages

- [[related-concept-1]]
- [[related-concept-2]]
```

## Citation rules

- Every factual claim references its source file.
- Use `(source: filename.pdf)` or `(source: filename.md)` after the claim (for PDFs, Jupyter notebooks, web clips, etc.).
- If two sources disagree, note the contradiction explicitly.
- If a claim has no source, mark it as needing verification.

## Answering questions

When the user asks a question:

1. Read `wiki/index.md` first to find relevant pages.
2. Read those pages and synthesize an answer.
3. Cite the specific wiki pages you drew from.
4. If the answer is not in the wiki, say so clearly.
5. If the answer is valuable, offer to save it as a new wiki page.

Good answers should be filed back into the wiki so they compound over time.

## Lint / audit

When asked to lint or audit the wiki:

- Check for contradictions between pages.
- Find orphan pages (no inbound links).
- Identify concepts mentioned inline that deserve their own page.
- Flag claims that may be outdated based on newer sources.
- Verify all pages follow the page format above.
- Rebuild the knowledge graph and report new orphan `Page` nodes, broken `REFERENCES` edges (wiki-link to nonexistent page), and `Source` nodes with no `CITES` parent.
- Report findings as a numbered list with suggested fixes.

## Knowledge graph

The wiki has structure beyond what `[[wiki-links]]` capture. Treat each page as a typed knowledge graph derived from its markdown hierarchy. `networkx`, `markdown-it-py`, and `tree-sitter` are already installed for this purpose. Persist graphs to `wiki/.graph/` so they can be queried, visualized in Neo4j/Gephi, or fed back into `query.py` for richer context selection.

### Node types

- `Page` — one `.md` file under `wiki/` (id = filename without extension).
- `Heading` — every `#`/`##`/`###`; carries `level`, `text`, `page`, and a `path` list (e.g. `["LangGraph Introduction", "Annotated", "기본 사용"]`).
- `CodeBlock` — every fenced block; carries `language`, `content`, `index_in_parent`.
- `Concept` — `[[wiki-link]]` target; resolves to a `Page` if the target file exists, else stays a stub.
- `Source` — file cited via the `**Sources**:` line or an inline `(source: filename)`.
- `Symbol` (optional) — Python identifier (class / function / import) extracted from a `CodeBlock` via `tree-sitter`.

### Relationship types — core spec

| Edge | From → To | When |
|------|-----------|------|
| `IS_NEXT` | sibling → next sibling | Two headings of the same level under the same parent, in document order. |
| `IS_BELONG_TO` | child → parent | A heading nested one level deeper, OR a code block appearing under a heading. |
| `HAS` | parent → child | Inverse of `IS_BELONG_TO` (emit both for traversal convenience). |
| `IS_NEXT_TO` | code block → next code block | Two adjacent fenced code blocks under the same heading, in document order. |

Every `IS_NEXT` / `IS_NEXT_TO` edge carries an `order: int` so sequences round-trip back to markdown.

### Relationship types — recommended extensions

1. **`REFERENCES`** — `Page → Page` for each `[[wiki-link]]`. Edge to a `Concept` stub when the target file does not exist (acts as an orphan-link detector).
2. **`CITES`** — `Page → Source` for each entry under `**Sources**:` and each inline `(source: filename)`. Lets the wiki answer "what came from this notebook?" in one query.
3. **`DEFINES` / `USES`** — `CodeBlock → Symbol`. Use the `tree-sitter` Python grammar so identifier extraction is robust (no regex). Example: a block containing `class Person(TypedDict):` emits `DEFINES → Person` and `USES → TypedDict`.
4. **`CONTAINS`** — `Page → Heading` for the page's top-level `#` heading only. Keeps the graph reachable from the page root without exploding edge count.
5. **`MENTIONS`** — `Heading → Symbol` when an inline backtick span (e.g. `` `add_messages` ``) matches a known `Symbol` node. Lightweight cross-reference without re-parsing prose.
6. **`TAGGED_AS`** — `Page → Tag` for Obsidian `#tag` lines and YAML frontmatter tags (when frontmatter is added later).

### Persistence

Write two files on every ingest:

- `wiki/.graph/graph.json` — `networkx.readwrite.json_graph.node_link_data(...)` (canonical, diffable).
- `wiki/.graph/graph.graphml` — `nx.write_graphml(...)` (Gephi / Neo4j / yEd compatible).

Use `networkx.MultiDiGraph` so multiple edge types can coexist between the same pair of nodes (e.g. both `HAS` and `MENTIONS` between a `Heading` and a `Symbol`).

### Worked example

Given this snippet from a wiki page:

````markdown
# LangGraph Introduction

## TypedDict

```python
class Person(TypedDict): ...
```

```python
typed_dict["age"] = 35
```

## Annotated

```python
from typing import Annotated
```
````

The graph contains:

- `Page(langgraph-introduction) HAS Heading(#:LangGraph Introduction)`
- `Heading(#) HAS Heading(##:TypedDict)` and `HAS Heading(##:Annotated)`
- `Heading(##:TypedDict) IS_NEXT Heading(##:Annotated)` (`order=0`)
- `Heading(##:TypedDict) HAS CodeBlock(0)` and `HAS CodeBlock(1)`
- `CodeBlock(0) IS_NEXT_TO CodeBlock(1)` (`order=0`)
- `CodeBlock(0) DEFINES Symbol(Person)` and `USES Symbol(TypedDict)`
- Inverse `IS_BELONG_TO` edge for every `HAS`

### Implementation note

Defer implementation to a follow-up task. When implementing: parse with `markdown-it-py`'s token stream (each token already carries `tag` and `level`); maintain a heading stack to assign parents; collect code blocks into the current heading's child list; emit edges in a single pass.

## Invariants

- Never modify anything in `raw/`.
- Always update `wiki/index.md` and `wiki/log.md` after changes.
- Page filenames are lowercase with hyphens (e.g. `machine-learning.md`).
- Write in clear, plain language.
- When uncertain about how to categorize something, ask the user.
- After every wiki write, regenerate `wiki/.graph/graph.json` and `wiki/.graph/graph.graphml`. The graph is a build artifact, never hand-edited.
