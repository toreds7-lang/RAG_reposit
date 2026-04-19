# LangGraph Notebook Annotator & Knowledge Graph Builder

A LangGraph agent that reads Jupyter notebooks, generates hierarchical markdown comments using OpenAI LLM, and builds an educational knowledge graph with semantic relationships.

## Features

### Core Features
- **Automated Comment Generation**: Uses GPT-4o-mini to generate hierarchical markdown comments (#, ##, ###)
- **Knowledge Graph Building**: Extracts relationships between sections and code cells
  - `IS_BELONG_TO`: Parent-child relationships (## → #, ### → ##, code → heading)
  - `IS_NEXT_TO`: Sibling relationships (sequential sections at same level)
- **Multiple Export Formats**: JSON, PNG visualization, NetworkX pickle, interactive HTML

### Extended Features
1. **Semantic Search**: Query the knowledge graph using natural language
2. **Variable Dependency Analysis**: Track data flow across code cells
3. **Interactive HTML Visualization**: Explore the graph with pyvis
4. **Quiz Generation**: Auto-generate fill-in-the-blank questions from code
5. **Multi-Notebook Curriculum Graphs**: Link related notebooks

## Installation

```bash
pip install -r requirements.txt
```

### Environment Setup
Create `env.txt` with your OpenAI API key:
```
OPENAI_API_KEY=sk-proj-...
```

## Quick Start

### Basic Usage
```bash
python agent.py --notebook my_notebook.ipynb --output-dir output
```

This generates:
- `output/annotated_notebook.ipynb` - Notebook with inserted markdown comments
- `output/knowledge_graph.json` - Graph structure
- `output/knowledge_graph.png` - Network visualization
- `output/knowledge_graph.gpickle` - NetworkX graph (Python)

### Example with Practice Notebook
```bash
python agent.py --notebook practice_notebook.ipynb --output-dir output
```

## Architecture

### LangGraph Workflow
```
START
  → read_notebook         (parse .ipynb cells)
  → generate_comments     (LLM generates # / ## / ### headers)
  → annotate_notebook     (inject markdown cells + save)
  → build_knowledge_graph (parse hierarchy → nodes + edges)
  → export_graph          (JSON + visualization)
END
```

### State Machine
The agent uses a `NotebookState` TypedDict that flows through all nodes:
```python
{
    "notebook_path": str,
    "raw_cells": list,              # Original cells
    "annotated_cells": list,        # With markdown inserted
    "knowledge_graph": dict,        # {nodes, edges}
    "output_notebook_path": str,
    "output_graph_path": str
}
```

## Knowledge Graph Format

### Nodes
```json
{
  "id": "heading_0",
  "type": "HEADING",              // or "CODE_CELL"
  "level": 1,                     // heading depth (1=H1, 2=H2, etc)
  "text": "Importing Libraries",
  "source": "# Importing Libraries\n..."
}
```

### Edges
```json
{
  "source": "code_1",
  "target": "heading_0",
  "type": "IS_BELONG_TO"          // or "IS_NEXT_TO"
}
```

## Extended Utilities

### 1. Semantic Search
```python
from utils.semantic_search import query_graph_semantic

results = query_graph_semantic(
    "visualization and plotting",
    "output/knowledge_graph.json"
)
# Returns top 5 semantically similar nodes
```

### 2. AST-Based Dependency Analysis
```python
from utils.ast_analyzer import analyze_code_dependencies

deps = analyze_code_dependencies(cells)
# Returns variable flow graph:
# {
#   0: {"assigns": ["df"], "uses": ["pd"], "depends_on": []}
#   1: {"assigns": [], "uses": ["df"], "depends_on": [{"cell_index": 0, ...}]}
# }
```

### 3. Quiz Generation
```python
from utils.quiz_generator import generate_quiz_from_graph

quiz = generate_quiz_from_graph(
    "output/knowledge_graph.gpickle",
    cells,
    "output/quiz.json"
)
# Auto-generates fill-in-the-blank questions from code
```

### 4. Interactive HTML Visualization
```bash
# Requires pyvis: pip install pyvis
python -c "from utils.interactive_viz import create_interactive_html_graph; \
           create_interactive_html_graph('output/knowledge_graph.json', \
                                        'output/knowledge_graph.gpickle', \
                                        'output/graph.html')"
```

Open `output/graph.html` in a browser to explore the graph interactively.

### 5. Cytoscape Export
```python
from utils.interactive_viz import export_to_cytoscape

export_to_cytoscape("output/knowledge_graph.json", "output/cytoscape.json")
# Export for use in Cytoscape.js, yEd, or other graph tools
```

## Output Examples

### Knowledge Graph JSON Structure
For the practice notebook (sales data analysis), the graph contains:
- **16 nodes**: 10 heading sections + 6 code cells
- **15 edges**: Parent-child (IS_BELONG_TO) + sibling (IS_NEXT_TO) relationships

Sample nodes:
```
- Heading: "# Importing Libraries" → children: import cells
- Heading: "## Essential Libraries..." → parent: "# Importing Libraries"
- Code: df setup cell → belongs to "# Creating Sample Sales Data"
```

### Network Visualization
The PNG visualization uses:
- **Blue nodes** (sized by heading level): Sections
- **Green nodes** (smaller): Code cells
- **Red arrows**: IS_BELONG_TO (hierarchy)
- **Blue dashed arrows**: IS_NEXT_TO (sequence)

## Customization

### Change LLM Model
Edit `nodes/generate_comments.py`:
```python
llm = ChatOpenAI(model="gpt-4-turbo", ...)  # or claude-3-sonnet-20240229, etc
```

### Adjust Comment Hierarchy
Modify the LLM system prompt in `generate_comments_node()`:
```python
system_prompt = """Use # for major topics, ## for subsections, ### for details..."""
```

### Add Custom Relationship Types
Extend `build_graph.py` to create new edge types:
```python
# Example: PREREQUISITE relationships based on semantic similarity
```

## Future Enhancements

1. **Incremental Updates**: Only regenerate comments for changed cells
2. **Multi-Notebook Linking**: Build curriculum graphs across notebooks
3. **Export to LMS**: Generate Moodle/Canvas packages with embedded quizzes
4. **Streaming Output**: Stream graph updates as they're computed
5. **Vector DB Integration**: Store embeddings in Pinecone/Weaviate for larger notebooks

## Testing

Run the agent on practice_notebook.ipynb:
```bash
python agent.py --notebook practice_notebook.ipynb --output-dir test_output
```

Verify outputs:
- ✓ `test_output/annotated_notebook.ipynb` has markdown cells
- ✓ `test_output/knowledge_graph.json` has 16+ nodes
- ✓ `test_output/knowledge_graph.png` displays graph
- ✓ Each ## node links to parent # node
- ✓ Sequential # nodes have IS_NEXT_TO edges

## Troubleshooting

### Issue: "OPENAI_API_KEY not found"
**Solution**: Check that `env.txt` exists and contains `OPENAI_API_KEY=sk-proj-...`

### Issue: LLM returns invalid JSON
**Solution**: The code has fallback behavior. Check LLM model availability or increase temperature.

### Issue: Graph has fewer nodes than expected
**Solution**: Not all cells get comments. Check which cells were recognized as headings in the JSON output.

### Issue: Interactive HTML won't load
**Solution**: Ensure `pyvis` is installed: `pip install pyvis>=0.3`

## License

MIT

## Author

Educational AI Tools
