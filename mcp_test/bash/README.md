# MCP Bash Agent

A LangChain-powered agent that executes bash commands on your local machine through the
[Model Context Protocol (MCP)](https://modelcontextprotocol.io/).
It connects to the **[mcp-bash](https://github.com/patrickomatik/mcp-bash)** server via
`langchain-mcp-adapters` and exposes an interactive chat loop where you can ask
Claude to run shell commands, navigate directories, and automate tasks.

---

## About the mcp-bash Server

**mcp-bash** is a lightweight MCP server written in Python that gives an LLM direct
access to a local shell. It exposes two tools over the MCP protocol:

| Tool | Parameters | Description |
|------|-----------|-------------|
| `set_cwd` | `path` (string) | Set the working directory for subsequent commands. Validates that the path exists. |
| `execute_bash` | `cmd` (string) | Run an arbitrary bash command and return stdout + stderr. |

The server maintains a global working directory (`GLOBAL_CWD`) that persists across
calls, so the agent can `cd` into a project and then run commands relative to it.

> **Security Warning**
> mcp-bash executes arbitrary shell commands with **no sandboxing or restrictions**.
> There is nothing preventing dangerous commands like `rm -rf /`.
> Only run this in a trusted, local environment. Never expose the server to untrusted
> users or networks.

---

## Prerequisites

- **Python 3.10+**
- **uv** (fast Python package manager) — [install guide](https://docs.astral.sh/uv/getting-started/installation/)
- **Git**
- An **Anthropic API key** (`ANTHROPIC_API_KEY`)

---

## Installation

### 1. Clone this repository (or copy files)

```bash
cd d:/2026_Agent/mcp_test/bash
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

```bash
# Windows (Git Bash / MSYS2)
source .venv/Scripts/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Clone the mcp-bash server

```bash
git clone https://github.com/patrickomatik/mcp-bash.git
```

### 6. Set up your API key

Create a `.env` file in the project root (if it doesn't already exist):

```
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
```

---

## Running the Agent

```bash
# Make sure the venv is activated
source .venv/Scripts/activate   # Windows Git Bash

python mcp_bash_agent.py
```

Expected output:

```
Connecting to MCP Bash server...
Loaded 2 tools: set_cwd, execute_bash

MCP Bash Agent ready. Type your instructions (or 'quit' to exit).

You:
```

---

## Test Examples

Below are interactive session examples you can try once the agent is running.

### Example 1 — List files

```
You: List all files in the current directory

Agent: I'll list the files in the current directory for you.
       [calls execute_bash with "ls -la"]
       Here are the files:
       - mcp_bash_agent.py
       - requirements.txt
       - .env
       - mcp-bash/
       - .venv/
```

### Example 2 — Set working directory and explore

```
You: Set the working directory to /tmp and show what's there

Agent: I'll set the working directory to /tmp and list its contents.
       [calls set_cwd with "/tmp"]
       [calls execute_bash with "ls -la"]
       The working directory is now /tmp. Here are the files: ...
```

### Example 3 — System information

```
You: Show system information - hostname, OS version, and disk usage

Agent: [calls execute_bash with "hostname && uname -a && df -h"]
       Hostname: MY-PC
       OS: MINGW64_NT-10.0-19045 ...
       Disk usage:
       Filesystem      Size  Used Avail Use% Mounted on
       ...
```

### Example 4 — Multi-step task: create and run a Python script

```
You: Create a directory called test_project, write a hello.py that prints "Hello from MCP!", then run it

Agent: I'll create the directory, write the script, and execute it.
       [calls execute_bash with "mkdir -p test_project"]
       [calls execute_bash with "echo 'print(\"Hello from MCP!\")' > test_project/hello.py"]
       [calls execute_bash with "python test_project/hello.py"]
       Done! Output: Hello from MCP!
```

### Example 5 — Git operations

```
You: Initialize a git repo in test_project, add all files, and make an initial commit

Agent: [calls set_cwd with "test_project"]
       [calls execute_bash with "git init"]
       [calls execute_bash with "git add ."]
       [calls execute_bash with "git commit -m 'Initial commit'"]
       Git repository initialized and initial commit created.
```

### Example 6 — Check network connectivity

```
You: Ping google.com 3 times and show the results

Agent: [calls execute_bash with "ping -c 3 google.com"]
       PING google.com (142.250.x.x): 56 data bytes
       64 bytes from 142.250.x.x: icmp_seq=0 ttl=117 time=12.3 ms
       ...
       3 packets transmitted, 3 received, 0% packet loss
```

---

## Project Structure

```
d:/2026_Agent/mcp_test/bash/
├── .env                  # API keys (ANTHROPIC_API_KEY)
├── .venv/                # Python virtual environment
├── mcp_bash_agent.py     # Main agent script
├── requirements.txt      # Python dependencies
├── mcp-bash/             # Cloned mcp-bash server repo
│   └── server.py         # MCP server that exposes bash tools
└── README.md             # This file
```

---

## How It Works

1. **mcp_bash_agent.py** launches the mcp-bash `server.py` as a subprocess using
   `uv run --with mcp[cli] mcp run server.py`
2. Communication happens over **stdio** using the MCP protocol
3. `langchain-mcp-adapters` converts the MCP tools into LangChain-compatible tools
4. A **LangGraph ReAct agent** (powered by Claude) decides when and how to call
   `set_cwd` and `execute_bash` based on your natural language instructions
5. Responses stream back token-by-token for a real-time chat experience

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| `Error: server.py not found` | Run `git clone https://github.com/patrickomatik/mcp-bash.git` in the project directory |
| `uv: command not found` | Install uv: `pip install uv` or see [uv docs](https://docs.astral.sh/uv/) |
| `ANTHROPIC_API_KEY not set` | Add your key to the `.env` file |
| Agent hangs on startup | Ensure `uv` is installed and `mcp[cli]` is available |
