# PowerPoint MCP Agent

AI-powered PowerPoint presentation creator and editor using LangChain + MCP (Model Context Protocol).

This agent connects to the [Office-PowerPoint-MCP-Server](https://github.com/GongRzhe/Office-PowerPoint-MCP-Server) which exposes ~34 specialized tools for creating, editing, and designing PowerPoint presentations programmatically through natural language.

## About the MCP Server

<!-- Office-PowerPoint-MCP-Server (v2.0.7) -->
<!-- Repository archived as of March 3, 2026 -->
<!-- Uses python-pptx under the hood for .pptx file operations -->
<!-- Default transport: stdio (standard input/output) -->
<!-- Also supports HTTP transport and Docker deployment -->
<!-- Requires: python-pptx>=0.6.21, mcp[cli]>=1.8.0, Pillow>=8.0.0, fonttools>=4.0.0 -->

**Key capabilities:**
- **Presentation Management** - Create, open, save, and manage presentation properties
- **Content Management** - Add slides, text, images with enhancement capabilities
- **Structural Elements** - Tables, shapes, charts with customization
- **Templates** - 25+ built-in professional layouts
- **Professional Design** - Themes, typography, 9+ visual effects (shadows, glows, bevels)
- **Text Extraction** - Extract text from individual slides or entire presentations

## Setup

### 1. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install langchain-anthropic langchain-mcp-adapters langchain mcp python-dotenv
```

### 3. Configure Environment Variables

Create a `.env` file (or use the existing one):

```
ANTHROPIC_API_KEY=your-anthropic-api-key
```

### 4. Ensure `uvx` is Available

The agent uses `uvx` to launch the MCP server. Install it via:

```bash
pip install uv
```

### 5. Run the Agent

```bash
python ppt_mcp_agent.py
```

## Test Examples

Once the agent is running, try these prompts:

### Example 1: Basic Presentation
```
You: Create a new presentation and add 3 slides about Machine Learning.
     Slide 1: Title slide with "Introduction to Machine Learning".
     Slide 2: What is ML with bullet points.
     Slide 3: Types of ML (supervised, unsupervised, reinforcement).
     Save it as ml_intro.pptx
```

### Example 2: Business Report
```
You: Create a professional business presentation with 5 slides.
     Use a corporate theme. Include a title slide for "Q1 2026 Sales Report",
     a slide with a table showing monthly revenue (Jan: $50K, Feb: $62K, Mar: $71K),
     a summary slide with key takeaways, and save it as q1_report.pptx
```

### Example 3: Using Templates
```
You: Create a presentation using a professional template.
     The topic is "Project Proposal: AI Chatbot".
     Include slides for objectives, timeline, budget, and team.
     Apply a modern blue color scheme and save as project_proposal.pptx
```

### Example 4: Image and Design
```
You: Create a 4-slide presentation about our company.
     Apply professional design with elegant green theme.
     Add shadow and glow effects to the title text.
     Save as company_overview.pptx
```

### Example 5: Edit Existing Presentation
```
You: Open the file ml_intro.pptx, add a new slide at the end
     with the title "Resources" and add 3 bullet points with
     recommended ML learning resources. Save the updated file.
```

### Example 6: Extract Text
```
You: Open ml_intro.pptx and extract all text from every slide.
     Show me a summary of the content.
```
