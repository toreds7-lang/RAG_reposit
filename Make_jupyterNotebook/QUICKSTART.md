# Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set API Key
Create `env.txt`:
```
OPENAI_API_KEY=sk-proj-your-key-here
```

### 3. Run Agent
```bash
python agent.py --notebook practice_notebook.ipynb --output-dir output
```

**Output**:
- `output/annotated_notebook.ipynb` — Notebook with markdown comments
- `output/knowledge_graph.json` — Graph structure
- `output/knowledge_graph.png` — Network visualization

Done! Check `output/` directory.

---

## What Each Component Does

### Core Workflow (agent.py)
```
Read notebook → LLM generates comments → Insert markdown → Build graph → Export formats
```

Takes 10-15 seconds for a typical notebook.

### Your Own Notebook
```bash
python agent.py --notebook my_notebook.ipynb --output-dir my_output
```

Replace `my_notebook.ipynb` with your file path.

---

## Exploring the Results

### 1. View Annotated Notebook
```bash
jupyter notebook output/annotated_notebook.ipynb
```
See the LLM-generated markdown comments inserted before code sections.

### 2. View Network Graph
Open `output/knowledge_graph.png` in any image viewer.
- **Blue nodes** = Section headers (sized by importance)
- **Green nodes** = Code cells
- **Red arrows** = Hierarchy (belongs-to)
- **Blue dashed arrows** = Sequence (next-to)

### 3. Interactive Exploration
```bash
# Windows
start output/graph_interactive.html

# Mac
open output/graph_interactive.html

# Linux
xdg-open output/graph_interactive.html
```
Drag nodes around, zoom, hover for details.

---

## Advanced Usage

### Semantic Search
Find related concepts using natural language:
```python
from utils.semantic_search import query_graph_semantic

# Search for visualization-related concepts
results = query_graph_semantic(
    "plotting and visualization", 
    "output/knowledge_graph.json"
)
for match in results["matches"]:
    print(f"{match['node']['text']} (score: {match['score']:.2f})")
```

### Variable Dependency Analysis
See which cells depend on which:
```python
from utils.ast_analyzer import analyze_code_dependencies
import nbformat

with open("output/annotated_notebook.ipynb") as f:
    nb = nbformat.read(f, as_version=4)

cells = [{"type": c.cell_type, "source": c.source} for c in nb.cells]
deps = analyze_code_dependencies(cells)

# Cell 3 depends on: cell 0, cell 1
print(deps[3]["depends_on"])
```

### Auto-Generated Quiz
Create educational questions:
```python
from utils.quiz_generator import generate_quiz_from_graph
import nbformat

with open("output/annotated_notebook.ipynb") as f:
    nb = nbformat.read(f, as_version=4)

cells = [{"type": c.cell_type, "source": c.source} for c in nb.cells]
quiz = generate_quiz_from_graph(
    "output/knowledge_graph.gpickle",
    cells,
    "output/quiz.json"
)

for q in quiz:
    print(f"Q: {q['question']}")
    print(f"A: {q['answer']}\n")
```

### Use Graph in Other Tools
Export to Cytoscape format (for yEd, Cytoscape.js, etc.):
```python
from utils.interactive_viz import export_to_cytoscape
export_to_cytoscape("output/knowledge_graph.json", "output/cytoscape.json")
```

---

## Command Reference

```bash
# Basic run
python agent.py --notebook my.ipynb --output-dir out

# Custom output directory
python agent.py --notebook data_analysis.ipynb --output-dir results/

# Run all demos
python demo.py
```

---

## Output Files Explained

| File | Format | Use Case |
|------|--------|----------|
| `annotated_notebook.ipynb` | Jupyter | View in Jupyter, share with others |
| `knowledge_graph.json` | JSON | Parse programmatically, web APIs |
| `knowledge_graph.png` | PNG | Include in presentations, docs |
| `knowledge_graph.gpickle` | Binary | Python queries, NetworkX analysis |
| `graph_interactive.html` | HTML | Explore interactively in browser |
| `cytoscape.json` | JSON | Use in Cytoscape.js or desktop tools |

---

## Customization

### Change LLM Model
Edit `nodes/generate_comments.py`, line ~43:
```python
llm = ChatOpenAI(
    api_key=api_key,
    model="gpt-4-turbo",  # Change this
    temperature=0.7,
)
```

### Adjust Comment Style
Edit `nodes/generate_comments.py`, system prompt (~25):
```python
system_prompt = """You are an expert educator...
Use # for major topics, ## for subsections, ### for details.
Add examples and context."""
```

### Change Output Directory
```bash
python agent.py --notebook my.ipynb --output-dir custom/path
```

---

## Troubleshooting

### "OPENAI_API_KEY not found"
- Verify `env.txt` exists in the project directory
- Check the file contains: `OPENAI_API_KEY=sk-proj-...`

### "ModuleNotFoundError: No module named 'langgraph'"
- Run: `pip install -r requirements.txt`

### Graph has fewer nodes than expected
- Not all code cells get comments
- Check `output/knowledge_graph.json` for actual structure
- LLM may skip redundant sections

### Interactive HTML won't open
- Ensure `pyvis` is installed: `pip install pyvis`
- Try opening the file directly in browser

---

## Examples

### Example 1: Simple Data Analysis
```bash
python agent.py --notebook my_sales_analysis.ipynb
# Output: Sales analysis with comment structure
```

### Example 2: Learn from Annotated Notebook
1. Run agent on tutorial notebook
2. Open `annotated_notebook.ipynb` in Jupyter
3. Read LLM-generated comments first
4. Understand code within that context

### Example 3: Create Study Material
```bash
python agent.py --notebook tutorial.ipynb --output-dir study/
# Then use utils/quiz_generator to create quiz
```

---

## Performance Tips

- **First run is slow** (15-20s) due to LLM calls
- For 100+ cells, consider splitting into smaller notebooks
- Embedding queries are fast (<1s) after first generation

---

## Next Steps

1. ✓ Run on your own notebooks
2. ✓ Explore the generated graphs
3. ✓ Try semantic search queries
4. ✓ Generate quizzes for students
5. ✓ Export for use in other tools

For detailed documentation, see [README.md](README.md) and [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md).
