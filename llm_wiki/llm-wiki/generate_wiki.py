#!/usr/bin/env python3
"""
Generate wiki markdown files from Jupyter notebooks.
Follows conventions in CLAUDE.md for the llm-wiki project.
"""

import json
from pathlib import Path
from datetime import datetime

raw_dir = Path('raw')
wiki_dir = Path('wiki')
wiki_dir.mkdir(exist_ok=True)

# Notebook metadata: filename -> (slug, notebook_name)
NOTEBOOKS = {
    '01-QuickStart-LangGraph-Tutorial.ipynb': ('quickstart-langgraph', 'QuickStart LangGraph Tutorial'),
    '01-LangGraph-Introduction.ipynb': ('langgraph-introduction', 'LangGraph Introduction'),
    '01-LangGraph-Building-Graphs.ipynb': ('langgraph-building-graphs', 'Building Graphs'),
    '01-LangGraph-Add-Memory.ipynb': ('langgraph-memory', 'Adding Memory'),
    '01-LangGraph-Models.ipynb': ('langgraph-models', 'LLM Models'),
    '01-LangGraph-Agents.ipynb': ('langgraph-agents', 'LangGraph Agents'),
    '01-LangGraph-Middleware.ipynb': ('langgraph-middleware', 'Middleware'),
    '01-LangGraph-Supervisor.ipynb': ('langgraph-supervisor', 'Supervisor Pattern'),
    '01-LangGraph-Agent-Simulation.ipynb': ('langgraph-agent-simulation', 'Agent Simulation'),
    '01-LangGraph-Text2Cypher-Neo4j.ipynb': ('langgraph-text2cypher', 'Text2Cypher Neo4j'),
    '01-LangGraph-MCP-Tutorial.ipynb': ('langgraph-mcp', 'MCP Tutorial'),
}

# Per-page related links (by slug) — curated neighbours for meaningful [[wiki-links]].
RELATED = {
    'quickstart-langgraph': ['langgraph-introduction', 'langgraph-building-graphs', 'langgraph-agents'],
    'langgraph-introduction': ['langgraph-building-graphs', 'langgraph-memory'],
    'langgraph-building-graphs': ['langgraph-introduction', 'langgraph-memory', 'langgraph-models'],
    'langgraph-memory': ['langgraph-building-graphs', 'langgraph-models'],
    'langgraph-models': ['langgraph-agents', 'langgraph-middleware'],
    'langgraph-agents': ['langgraph-models', 'langgraph-middleware', 'langgraph-supervisor'],
    'langgraph-middleware': ['langgraph-agents', 'langgraph-supervisor'],
    'langgraph-supervisor': ['langgraph-agents', 'langgraph-agent-simulation'],
    'langgraph-agent-simulation': ['langgraph-supervisor', 'langgraph-agents'],
    'langgraph-text2cypher': ['langgraph-mcp', 'langgraph-agents'],
    'langgraph-mcp': ['langgraph-text2cypher', 'langgraph-agents'],
}


def extract_notebook_content(nb_path):
    """Extract markdown and code cells from a notebook in document order."""
    with open(nb_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    cells = []
    for cell in nb['cells']:
        source = cell.get('source', '')
        if isinstance(source, list):
            source = ''.join(source)
        if not source.strip():
            continue
        if cell['cell_type'] in ('markdown', 'code'):
            cells.append({'type': cell['cell_type'], 'source': source})
    return cells


def create_summary_page(nb_file, slug, title, cells):
    """Create a wiki page for the notebook, following CLAUDE.md page format."""
    today = datetime.now().strftime('%Y-%m-%d')
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Summary**: Learning material extracted from {nb_file.name}.")
    lines.append("")
    lines.append(f"**Sources**: {nb_file.name}")
    lines.append("")
    lines.append(f"**Last updated**: {today}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, cell in enumerate(cells):
        src = cell['source'].rstrip()
        if cell['type'] == 'markdown':
            # Skip the notebook's own top-level title if it duplicates ours.
            if i == 0:
                first_line = src.split('\n', 1)[0].lstrip()
                if first_line.startswith('# '):
                    rest = src.split('\n', 1)[1] if '\n' in src else ''
                    rest = rest.strip()
                    if rest:
                        lines.append(rest)
                        lines.append("")
                    continue
            lines.append(src)
            lines.append("")
        else:  # code
            lines.append("```python")
            lines.append(src)
            lines.append("```")
            lines.append("")

    # Page-level inline citation, per CLAUDE.md citation rules.
    lines.append(f"(source: {nb_file.name})")
    lines.append("")

    # Related pages — curated, never identical across every page.
    lines.append("## Related pages")
    lines.append("")
    for related in RELATED.get(slug, []):
        lines.append(f"- [[{related}]]")
    lines.append("")

    return '\n'.join(lines)


def main():
    summaries = []
    log_entries = []

    for nb_file, (slug, title) in NOTEBOOKS.items():
        nb_path = raw_dir / nb_file
        if not nb_path.exists():
            print(f"[WARN] {nb_file} not found")
            continue

        print(f"[INFO] Processing {nb_file}...")
        cells = extract_notebook_content(nb_path)
        if not cells:
            print(f"  [WARN] No content extracted")
            continue

        page_content = create_summary_page(nb_path, slug, title, cells)
        page_file = wiki_dir / f"{slug}.md"
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(page_content)
        print(f"  [OK] Created {page_file.name}")

        summaries.append((slug, title))
        log_entries.append(f"- {title} ({nb_file}) → [[{slug}]]")

    # index.md — link only to pages that actually exist.
    print("\n[INFO] Creating index...")
    today = datetime.now().strftime('%Y-%m-%d')
    learning_path_order = [
        ('quickstart-langgraph', 'Quick overview and setup'),
        ('langgraph-introduction', 'State and TypedDict fundamentals'),
        ('langgraph-building-graphs', 'Building graph structures'),
        ('langgraph-memory', 'Memory and state persistence'),
        ('langgraph-models', 'Working with LLM models'),
        ('langgraph-agents', 'Creating agents'),
        ('langgraph-middleware', 'Middleware patterns'),
        ('langgraph-supervisor', 'Supervisor multi-agent pattern'),
        ('langgraph-agent-simulation', 'Simulating and testing agents'),
        ('langgraph-text2cypher', 'Graph database queries with Cypher'),
        ('langgraph-mcp', 'Model Context Protocol integration'),
    ]
    existing_slugs = {slug for slug, _ in summaries}
    learning_path_lines = [
        f"{i}. [[{slug}]] — {desc}"
        for i, (slug, desc) in enumerate(learning_path_order, start=1)
        if slug in existing_slugs
    ]
    all_pages_lines = [f"- [[{slug}]]" for slug, _ in summaries]

    index_content = (
        "# LangGraph Tutorial Wiki\n\n"
        f"**Summary**: Table of contents for wiki pages generated from LangGraph tutorial notebooks in `raw/`.\n\n"
        f"**Last updated**: {today}\n\n"
        "---\n\n"
        "## Learning Path\n\n"
        + '\n'.join(learning_path_lines) + "\n\n"
        "## All Pages\n\n"
        + '\n'.join(all_pages_lines) + "\n\n"
        "---\n\n"
        "*This wiki is maintained from source Jupyter notebooks in `raw/`. Never edit `raw/` files directly.*\n"
    )
    (wiki_dir / "index.md").write_text(index_content, encoding='utf-8')
    print("  [OK] Created index.md")

    # log.md
    print("[INFO] Creating log...")
    log_content = (
        "# Wiki Ingest Log\n\n"
        f"## {today} - Regenerated wiki from notebooks\n\n"
        f"Generated {len(summaries)} pages from LangGraph tutorial notebooks in `raw/`.\n\n"
        "### Pages created\n"
        + '\n'.join(log_entries) + "\n\n"
        "---\n"
        "*Append-only log of wiki updates*\n"
    )
    (wiki_dir / "log.md").write_text(log_content, encoding='utf-8')
    print("  [OK] Created log.md")

    print(f"\n[DONE] Created {len(summaries)} pages.")


if __name__ == '__main__':
    main()
