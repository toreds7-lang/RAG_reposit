# Fetch MCP Agent

An interactive CLI agent that retrieves web content using the **MCP Fetch server** (`mcp-server-fetch`) as a tool backend, powered by **LangChain** and **Claude** (Anthropic).

## About the Server

The agent connects to [`mcp-server-fetch`](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) — an MCP (Model Context Protocol) server that exposes HTTP fetch capabilities as a tool. It allows the LLM to:

- Fetch the raw HTML or text content of any public URL
- Follow redirects and retrieve structured web content
- Pass retrieved content back to the LLM for summarization, extraction, or analysis

The server is launched automatically as a subprocess via `uvx mcp-server-fetch` each time the agent runs. No manual server startup is required.

---

## Prerequisites

- Python 3.10+
- [`uv`](https://github.com/astral-sh/uv) installed globally (used by `uvx` to run the MCP server)
  ```bash
  # Install uv (if not already installed)
  pip install uv
  # or on Windows via PowerShell:
  # irm https://astral.sh/uv/install.ps1 | iex
  ```

---

## Setup

### 1. Create and activate a virtual environment

```bash
# Create venv
python -m venv .venv

# Activate (Windows CMD)
.venv\Scripts\activate.bat

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Linux / macOS)
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install \
  langchain-anthropic \
  langchain-mcp-adapters \
  mcp \
  python-dotenv \
  langchain
```

Or if you add a `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env` and fill in your keys (never commit real keys to git):

```env
ANTHROPIC_API_KEY=sk-ant-...        # Required — used by ChatAnthropic
LANGSMITH_API_KEY=lsv2_pt_...       # Optional — enables LangSmith tracing
LANGSMITH_TRACING=true              # Optional — set false to disable tracing
LANGSMITH_PROJECT=LangGraph-Tutorial
```

---

## Run

```bash
python fetch_mcp_agent.py
```

You will see:

```
Connecting to Fetch MCP server...
Loaded 1 tools: fetch
Fetch Agent ready. Type your instructions (or 'quit' to exit).

You:
```

---

## Example Prompts

### Fetch and summarize a webpage

```
You: Fetch https://example.com and summarize the page content
```

### Extract specific data

```
You: Go to https://httpbin.org/json and tell me what fields are in the response
```

### Compare two pages

```
You: Fetch https://python.org and https://pypy.org, then compare their main features
```

### Get plain text from a URL

```
You: Retrieve the text from https://www.rfc-editor.org/rfc/rfc791 and give me the first paragraph
```

### Exit the agent

```
You: quit
```

---

## Project Structure

```
fetch/
├── fetch_mcp_agent.py   # Main agent entry point
├── .env                 # API keys (keep secret, add to .gitignore)
└── README.md            # This file
```

---

## How It Works

1. The agent starts an MCP `stdio` subprocess running `uvx mcp-server-fetch`.
2. LangChain's `load_mcp_tools` converts the server's tool manifest into LangChain tools.
3. A `ChatAnthropic` LLM is given those tools and wrapped with `create_agent`.
4. User messages are streamed through the agent, which decides when to call `fetch` and incorporates the results into its response.
