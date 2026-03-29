# Filesystem MCP Agent

Interactive file system operations powered by LangChain + MCP (Model Context Protocol).

## Prerequisites

- Python 3.10+
- Node.js 18+ (for `npx`)
- Anthropic API key

## Setup

```bash
# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install Python dependencies
pip install langchain-anthropic langchain-mcp-adapters langchain mcp python-dotenv

# Set your API key (create .env file)
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

## Run

```bash
# Activate venv first (if not already active)
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Default: allows access to current working directory
python filesystem_agent.py

# Specify allowed directories
python filesystem_agent.py D:\projects C:\data
```

## Test Sequence Examples

Once the agent is running, try these commands in order:

### 1. List files

```
You: List all files in the current directory
```

### 2. Read a file

```
You: Read the contents of filesystem_agent.py
```

### 3. Create a file

```
You: Create a file called hello.txt with the content "Hello from MCP agent!"
```

### 4. Verify the file was created

```
You: List all files again and show me the contents of hello.txt
```

### 5. Edit a file

```
You: Append a new line "This line was added by the agent." to hello.txt
```

### 6. Search files

```
You: Search for all .py files and tell me how many lines each has
```

### 7. Create a directory and files

```
You: Create a folder called test_output and add a file called notes.txt inside it with today's date
```

### 8. Get directory info

```
You: Show me a tree view of all files and folders in the current directory
```

### 9. Clean up

```
You: Delete hello.txt and the test_output folder
```

### 10. Exit

```
You: quit
```

## Available MCP Tools

The filesystem server provides these tools:

| Tool | Description |
|------|-------------|
| `read_file` | Read contents of a single file |
| `read_multiple_files` | Read contents of multiple files at once |
| `write_file` | Create or overwrite a file |
| `edit_file` | Make selective edits to a file |
| `create_directory` | Create a new directory (recursive) |
| `list_directory` | List files and directories |
| `move_file` | Move or rename a file/directory |
| `search_files` | Recursively search for files by name pattern |
| `get_file_info` | Get metadata (size, timestamps, permissions) |
| `list_allowed_directories` | Show which directories the server can access |
