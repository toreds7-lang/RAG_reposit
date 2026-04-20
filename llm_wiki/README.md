# LLM Wiki

A personal knowledge base built by Claude Code from raw source documents, following Andrej Karpathy's "LLM Wiki" pattern. Current scope: learning the LangGraph framework through structured wiki pages built from Jupyter tutorials.

This repo has two parts:
1. **Wiki building**: Claude Code and Python scripts read source Jupyter notebooks from the `raw/` folder and maintain structured markdown pages in the `wiki/` folder.
2. **Wiki querying**: A Python script (`query.py`) that lets you ask questions against the built wiki using GPT-4o.

---

## Repository Layout

```
llm-wiki/
├── llm-wiki/                 # Obsidian vault (the wiki itself)
│   ├── CLAUDE.md             # Instructions Claude Code reads on startup
│   ├── generate_wiki.py      # Script to generate wiki pages from Jupyter notebooks
│   ├── raw/                  # Source Jupyter notebooks (immutable)
│   │   ├── 01-QuickStart-LangGraph-Tutorial.ipynb
│   │   ├── 01-LangGraph-Introduction.ipynb
│   │   ├── 01-LangGraph-Building-Graphs.ipynb
│   │   ├── 01-LangGraph-Add-Memory.ipynb
│   │   ├── 01-LangGraph-Models.ipynb
│   │   ├── 01-LangGraph-Agents.ipynb
│   │   ├── 01-LangGraph-Middleware.ipynb
│   │   ├── 01-LangGraph-Supervisor.ipynb
│   │   ├── 01-LangGraph-Agent-Simulation.ipynb
│   │   ├── 01-LangGraph-Text2Cypher-Neo4j.ipynb
│   │   └── 01-LangGraph-MCP-Tutorial.ipynb
│   ├── wiki/                 # Claude-maintained wiki pages
│   │   ├── index.md          # Table of contents
│   │   ├── log.md            # Operation log
│   │   └── *.md              # Topic pages (langgraph-agents.md, langgraph-supervisor.md, etc.)
│   └── templates/            # Page templates (currently empty)
├── query.py                  # Interactive Q&A script
├── env.txt                   # OpenAI API key (not committed)
└── README.md                 # This file
```

---

## How CLAUDE.md Works

`CLAUDE.md` is the instruction manifest that Claude Code reads automatically when you open the project. It defines:

- **Directory roles**: `raw/` (immutable source notebooks), `wiki/` (maintained pages), `templates/` (future templates)
- **Ingest workflow**: How source Jupyter notebooks are converted into wiki pages
- **Page format**: Standard structure all wiki pages must follow (title, summary, sources, last updated, related pages)
- **Citation rules**: Every factual claim must cite its source
- **Lint/audit**: How to check for contradictions, orphan pages, and format violations

### The Ingest Flow

Two paths for wiki building:

**Automated Path**: Run `python generate_wiki.py` to automatically convert all `.ipynb` notebooks in `raw/` into structured wiki pages in `wiki/`.

**Manual/Interactive Path**: When you want to review changes with Claude before committing:

1. **Read**: Claude reads the full Jupyter notebook
2. **Discuss**: Claude discusses key takeaways with you before writing anything
3. **Create pages**: Claude creates pages in `wiki/` that extract concepts from the notebook
4. **Link**: Claude adds `[[wiki-links]]` between related pages
5. **Update index**: Claude updates `wiki/index.md` with new pages and descriptions
6. **Log**: Claude appends an entry to `wiki/log.md` recording what changed

A single Jupyter notebook typically seeds 10–15 wiki pages.

**Important**: Claude never modifies files in `raw/`. They are the authoritative source.

---

## How to Build the Wiki

### Prerequisites
- Python 3.8+ with dependencies: `langchain`, `langchain-openai`, `tiktoken`
- Claude Code (VS Code extension, CLI, or web at claude.ai/code)
- The `llm-wiki/llm-wiki/` folder open in Claude Code (for interactive updates)

### Adding a New Source

**Option 1: Automated (Recommended)**

1. **Save a Jupyter notebook** into `llm-wiki/llm-wiki/raw/` as a `.ipynb` file
2. **Run the generation script**:
   ```bash
   cd llm-wiki/llm-wiki/
   python generate_wiki.py
   ```
3. **Verify the update**
   - Check `wiki/index.md` to see the new pages
   - Check `wiki/log.md` to confirm the operation was logged

**Option 2: Interactive (with Claude Code)**

1. **Save a Jupyter notebook** into `llm-wiki/llm-wiki/raw/` as a `.ipynb` file
2. **Tell Claude to ingest it**
   - Open the project folder `llm-wiki/llm-wiki/` in Claude Code
   - Message Claude: `"ingest raw/<filename>.ipynb"`
3. **Review and approve**
   - Claude will discuss the key takeaways
   - Review the proposed wiki pages
   - Approve the changes
4. **Verify the update**
   - Check `wiki/index.md` to see the new pages
   - Check `wiki/log.md` to confirm the operation was logged

---

## How to Query the Wiki

`query.py` is an interactive Q&A script that loads all wiki pages and answers questions using GPT-4o.

### Setup (First Time)

```bash
# Create and activate a Python virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# or: source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install langchain langchain-openai
```

### Running Queries

```bash
# Activate the virtual environment (if not already active)
.venv\Scripts\activate          # Windows
# or: source .venv/bin/activate  # Mac/Linux

# Add your OpenAI API key to env.txt
echo "OPENAI_API_KEY=sk-..." > env.txt

# Start the interactive Q&A session
python query.py
```

What happens:
- The script loads all `.md` files from `wiki/`
- It starts an interactive loop where you can type questions
- For each question, GPT-4o reads the entire wiki and synthesizes an answer
- Answers include citations showing which wiki pages were used (e.g., "source: osaka-food-culture.md")
- Type `quit` to exit

### Example Questions

```
Question: What is a StateGraph in LangGraph?
Question: How does memory persistence work in LangGraph?
Question: What is the Supervisor multi-agent pattern?
Question: How do I add middleware to a LangGraph agent?
Question: What models does LangGraph support?
```

---

## Security Note

`env.txt` contains a plaintext OpenAI API key. **Do not commit it to version control.**

If you have a `.gitignore`, add:
```
env.txt
```

---

## Structure of a Wiki Page

Every wiki page follows this template (defined in `CLAUDE.md`):

```markdown
# Page Title

**Summary**: One to two sentences describing this page.

**Sources**: List of raw source files this page draws from.

**Last updated**: Date of most recent update.

---

Main content with clear headings and short paragraphs.

Link to related concepts using [[wiki-links]] throughout.

## Related pages

- [[related-concept-1]]
- [[related-concept-2]]
```

Key rules:
- Every factual claim cites its source: `(source: filename.md)`
- If two sources contradict, the contradiction is noted explicitly
- Page filenames are lowercase with hyphens (e.g., `osaka-castle.md`)
- The `[[wiki-links]]` enable navigation and relationship tracking

---

## Understanding the Wiki Index and Log

### `wiki/index.md` — Table of Contents
A hierarchical overview of all wiki pages, grouped by topic (e.g., Attractions, Food, Districts). Updated whenever Claude creates or renames a page.

### `wiki/log.md` — Operation Log
An append-only record of every ingestion, update, and audit. Each entry logs:
- Date and time
- Source file ingested (or operation performed)
- What pages were created or modified

This log is your audit trail for understanding how the wiki evolved.

---

## Typical Workflow

1. **Find a source**: Web clip, PDF, Jupyter notebook, article, etc.
2. **Drop it into `raw/`**: Save it as a markdown file
3. **Ingest in Claude Code**: Tell Claude to process it
4. **Review pages**: Approve the wiki pages Claude created
5. **Ask questions**: Use `query.py` to ask questions against the wiki
6. **Refine as needed**: Ingest more sources, update pages, ask follow-ups

---

## Tips

- **Jupyter notebooks**: Place raw `.ipynb` notebooks directly in `raw/`. They are the primary source format and are ingested as-is by `generate_wiki.py`.
- **Notebook structure**: Notebooks with clear markdown headings and cell-level organization work best—Claude can extract concept pages aligned with the notebook's structure.
- **Incomplete sources**: If a source is incomplete or needs manual cleanup, do it before ingestion—the ingest process will read it as-is.
- **Large sources**: Claude and the generation script handle large notebooks well; a single notebook can seed 10–15 wiki pages.
- **Linking**: Use `[[page-name]]` to link between pages in the wiki. These links make the wiki navigable in Obsidian or as a web view.
- **Citation**: When querying the wiki, the script cites which pages it used. Check those pages directly if you want more detail.

---

## For More Information

- **CLAUDE.md**: Full instructions Claude Code follows when working with this project
- **wiki/index.md**: Current table of contents and all wiki pages
- **wiki/log.md**: Complete history of all ingestions and updates
- **query.py**: Python source code for the wiki query script
