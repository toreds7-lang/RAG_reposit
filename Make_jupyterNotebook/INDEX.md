# LangGraph Notebook Annotator - Project Index

## 📚 Documentation

| File | Purpose |
|------|---------|
| [QUICKSTART.md](QUICKSTART.md) | **START HERE** — 5-minute setup and basic usage |
| [README.md](README.md) | Complete feature documentation and API reference |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Deep dive into architecture, design decisions, implementation details |
| [INDEX.md](INDEX.md) | This file — project overview and file guide |

## 🚀 Getting Started

1. **Install**: `pip install -r requirements.txt`
2. **Configure**: Create `env.txt` with `OPENAI_API_KEY=sk-proj-...`
3. **Run**: `python agent.py --notebook practice_notebook.ipynb --output-dir output`
4. **Explore**: Open `output/annotated_notebook.ipynb` or `output/graph_interactive.html`

See [QUICKSTART.md](QUICKSTART.md) for detailed instructions.

---

## 📁 Project Structure

```
Make_jupyterNotebook/
├── CORE ENTRY POINTS
│   ├── agent.py              ← Main LangGraph orchestrator
│   └── demo.py               ← Demo script showcasing all features
│
├── PIPELINE NODES (LangGraph workflow)
│   └── nodes/
│       ├── read_notebook.py        ← Parse .ipynb files
│       ├── generate_comments.py    ← LLM-powered markdown generation
│       ├── annotate_notebook.py    ← Inject markdown cells
│       ├── build_graph.py          ← Construct knowledge graph
│       └── export_graph.py         ← Generate visualizations
│
├── EXTENDED UTILITIES (advanced features)
│   └── utils/
│       ├── semantic_search.py      ← Natural language graph queries
│       ├── ast_analyzer.py         ← Variable dependency analysis
│       ├── quiz_generator.py       ← Auto-generate quiz questions
│       └── interactive_viz.py      ← HTML & Cytoscape exports
│
├── CONFIGURATION & DATA
│   ├── env.txt                      ← OpenAI API key (user-provided)
│   ├── requirements.txt             ← Python dependencies
│   └── practice_notebook.ipynb      ← Test/example notebook
│
├── DOCUMENTATION
│   ├── QUICKSTART.md                ← Quick start guide
│   ├── README.md                    ← Full documentation
│   ├── PROJECT_SUMMARY.md           ← Architecture & design
│   └── INDEX.md                     ← This file
│
└── output/ (generated at runtime)
    ├── annotated_notebook.ipynb     ← Input + markdown comments
    ├── knowledge_graph.json         ← Graph structure
    ├── knowledge_graph.png          ← Network visualization
    ├── knowledge_graph.gpickle      ← NetworkX format
    ├── graph_interactive.html       ← Interactive explorer
    ├── cytoscape.json               ← Cytoscape format
    └── quiz.json                    ← Generated quiz questions
```

---

## 🎯 Use Cases

### 1. **Document Your Notebooks** (Educational)
```bash
python agent.py --notebook my_tutorial.ipynb --output-dir tutorial_docs/
# Generates automatically-documented notebook with markdown comments
```

### 2. **Build Knowledge Graphs** (Knowledge Management)
```python
# Access the graph as JSON for custom analysis
import json
with open("output/knowledge_graph.json") as f:
    graph = json.load(f)
# Use for question answering, concept mapping, etc.
```

### 3. **Semantic Search** (Discovery)
```python
from utils.semantic_search import query_graph_semantic
results = query_graph_semantic("data visualization", "output/knowledge_graph.json")
# Find related concepts without knowing exact keywords
```

### 4. **Generate Quizzes** (Assessment)
```python
from utils.quiz_generator import generate_quiz_from_graph
quiz = generate_quiz_from_graph("output/knowledge_graph.gpickle", cells, "quiz.json")
# Create educational assessments automatically
```

### 5. **Track Data Flow** (Debugging)
```python
from utils.ast_analyzer import analyze_code_dependencies
deps = analyze_code_dependencies(cells)
# See which cells produce data used by other cells
```

---

## 📊 Architecture Overview

### LangGraph Workflow
```
read_notebook
    ↓ (raw_cells)
generate_comments
    ↓ (LLM adds markdown)
annotate_notebook
    ↓ (saves .ipynb)
build_knowledge_graph
    ↓ (creates graph structure)
export_graph
    ↓ (JSON, PNG, HTML, pickle)
[output files]
```

### Knowledge Graph
- **Nodes**: Headings (# / ## / ###) + Code cells
- **Edges**: 
  - `IS_BELONG_TO` — Hierarchical containment
  - `IS_NEXT_TO` — Sequential sections
- **Format**: JSON, NetworkX, HTML, Cytoscape

### LLM Integration
- **Model**: `gpt-4o-mini` (cost-efficient)
- **Task**: Generate hierarchical markdown comments
- **Input**: Python code snippets
- **Output**: # / ## / ### headers with explanations

---

## 🔧 API Quick Reference

### Main Entry Point
```python
from agent import create_agent

agent = create_agent()
initial_state = {
    "notebook_path": "my.ipynb",
    "raw_cells": [],
    "annotated_cells": [],
    "knowledge_graph": {"nodes": [], "edges": []},
    "output_notebook_path": "output/annotated.ipynb",
    "output_graph_path": "output",
}
result = agent.invoke(initial_state)
```

### Semantic Search
```python
from utils.semantic_search import query_graph_semantic, get_node_context

# Find related concepts
results = query_graph_semantic("topic", "knowledge_graph.json")

# Get context for a node
context = get_node_context("heading_0", "knowledge_graph.json", "knowledge_graph.gpickle")
```

### Code Analysis
```python
from utils.ast_analyzer import analyze_code_dependencies, extract_assignments_and_uses

# Full dependency graph
deps = analyze_code_dependencies(cells)

# Single cell analysis
assigned, used = extract_assignments_and_uses(code)
```

### Quiz Generation
```python
from utils.quiz_generator import generate_quiz_from_graph, save_quiz

quiz = generate_quiz_from_graph("knowledge_graph.gpickle", cells, "quiz.json")
```

### Visualization
```python
from utils.interactive_viz import create_interactive_html_graph, export_to_cytoscape

create_interactive_html_graph("knowledge_graph.json", "knowledge_graph.gpickle", "graph.html")
export_to_cytoscape("knowledge_graph.json", "cytoscape.json")
```

---

## 📈 Expected Outputs

### For a Typical 8-Cell Notebook
- **16 graph nodes**: ~10 heading levels + ~6 code cells
- **15 graph edges**: Parent-child relationships + sequence links
- **Processing time**: 10-15 seconds (mostly LLM API calls)

### Generated Files
| File | Size | Type | Readability |
|------|------|------|------------|
| annotated_notebook.ipynb | 5-10 KB | Jupyter | ⭐⭐⭐ |
| knowledge_graph.json | 5-10 KB | JSON | ⭐⭐ |
| knowledge_graph.png | 100-300 KB | PNG | ⭐⭐⭐ |
| knowledge_graph.gpickle | 1-5 KB | Binary | Machine-readable |
| graph_interactive.html | 10-50 KB | HTML | ⭐⭐⭐ |

---

## 🧪 Testing & Validation

### Automated Testing
```bash
python agent.py --notebook practice_notebook.ipynb --output-dir test_output
```

### Manual Verification
- ✅ Annotated notebook opens in Jupyter
- ✅ Comments are coherent and hierarchical
- ✅ PNG visualization renders correctly
- ✅ Interactive HTML loads in browser
- ✅ JSON parses without errors

---

## 🎓 Learning Resources

### Understand the Project
1. **Start with**: [QUICKSTART.md](QUICKSTART.md) (5 min)
2. **Deep dive**: [README.md](README.md) (15 min)
3. **Architecture**: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) (20 min)

### Code Study
1. `agent.py` — LangGraph workflow (50 lines)
2. `nodes/generate_comments.py` — LLM integration (60 lines)
3. `nodes/build_graph.py` — Hierarchy parsing (80 lines)
4. `utils/semantic_search.py` — Embeddings (70 lines)

---

## 🚨 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `OPENAI_API_KEY not found` | Create `env.txt` with API key |
| `ModuleNotFoundError: langgraph` | Run `pip install -r requirements.txt` |
| LLM returns invalid JSON | Fallback triggered; check output manually |
| Graph has fewer nodes | Not all cells get comments; check JSON |
| Interactive HTML blank | Ensure `pyvis` installed; open in modern browser |

See [QUICKSTART.md](QUICKSTART.md#troubleshooting) for more troubleshooting.

---

## 🔮 Future Roadmap

### Implemented ✅
- ✅ LangGraph agent pipeline
- ✅ Hierarchical markdown generation
- ✅ Knowledge graph construction
- ✅ Semantic search
- ✅ Variable dependency analysis
- ✅ Quiz generation
- ✅ Interactive visualization

### Planned 🔄
- 🔄 Incremental updates (skip unchanged cells)
- 🔄 Multi-notebook curriculum graphs
- 🔄 Vector DB integration (Pinecone/Weaviate)
- 🔄 LMS export (Moodle/Canvas)
- 🔄 Streaming updates
- 🔄 Custom heading/relationship templates

---

## 📞 Support

For detailed questions:
- **Quick help**: [QUICKSTART.md](QUICKSTART.md)
- **Feature docs**: [README.md](README.md)
- **Architecture**: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- **Code**: Check docstrings in `.py` files

---

## 📄 Files at a Glance

| File | Lines | Purpose |
|------|-------|---------|
| agent.py | ~90 | Main orchestrator |
| nodes/read_notebook.py | ~30 | Notebook parsing |
| nodes/generate_comments.py | ~65 | LLM comment generation |
| nodes/annotate_notebook.py | ~35 | Markdown injection |
| nodes/build_graph.py | ~85 | Graph construction |
| nodes/export_graph.py | ~85 | Visualization & export |
| utils/semantic_search.py | ~95 | Semantic queries |
| utils/ast_analyzer.py | ~80 | Variable analysis |
| utils/quiz_generator.py | ~50 | Quiz generation |
| utils/interactive_viz.py | ~85 | HTML & Cytoscape |
| **TOTAL** | **~700** | **Minimal, readable codebase** |

---

## ✨ Highlights

🎯 **Complete Pipeline** — From notebook to knowledge graph in one command
🧠 **AI-Powered** — Uses GPT-4o-mini for intelligent comment generation
📊 **Multiple Formats** — JSON, PNG, HTML, Cytoscape, NetworkX
🔍 **Semantic Queries** — Search the graph with natural language
🎓 **Educational Focus** — Designed for learning and knowledge extraction
🔧 **Extensible** — Modular design makes it easy to add features

---

**Ready to get started?** See [QUICKSTART.md](QUICKSTART.md)
