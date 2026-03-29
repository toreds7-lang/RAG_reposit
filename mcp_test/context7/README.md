# Context7 MCP Agent

Library documentation lookup agent using LangChain + Context7 MCP server (`@upstash/context7-mcp`).

## Setup

### 1. Create virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install langchain-anthropic langchain-mcp-adapters langchain mcp python-dotenv
```

### 3. Configure environment variables

Create a `.env` file (or edit the existing one) with your API key:

```env
ANTHROPIC_API_KEY=your-api-key-here
```

### 4. Run the agent

```bash
python context7_agent.py
```

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `resolve-library-id` | Resolves a library name (e.g. "react") into a Context7-compatible library ID |
| `get-library-docs` | Retrieves documentation for a given Context7 library ID |

## Test Examples

### 1. Resolve a library ID

```
You: Find the Context7 library ID for Next.js
```

The agent will call `resolve-library-id` with "next.js" and return the matching library ID (e.g. `/vercel/next.js`).

### 2. Query library documentation

```
You: Get the documentation for React hooks
```

The agent will first resolve the library ID for React, then call `get-library-docs` to retrieve relevant documentation about hooks.

### 3. Look up a specific topic

```
You: How does routing work in Next.js? use context7
```

The agent resolves the Next.js library ID and fetches documentation focused on the "routing" topic.

### 4. Explore an unfamiliar library

```
You: What is Zustand and how do I use it for state management?
```

The agent resolves the Zustand library ID and retrieves getting-started documentation with code examples.

### 5. Compare library APIs

```
You: Show me how to make HTTP requests using Axios
```

The agent resolves the Axios library ID and returns documentation with request examples and configuration options.

### 6. Framework-specific setup

```
You: How do I set up authentication in a Nuxt.js app?
```

The agent resolves the Nuxt.js library ID and fetches documentation related to authentication modules and middleware.

### 7. Database library usage

```
You: Show me how to define models and run queries with Prisma
```

The agent resolves the Prisma library ID and retrieves documentation covering schema definition and query examples.

## How It Works

1. The agent connects to the Context7 MCP server via `npx @upstash/context7-mcp@latest`
2. It loads the available tools (`resolve-library-id`, `get-library-docs`)
3. When you ask a question, the LLM decides which tools to call
4. `resolve-library-id` maps a library name to a Context7 ID
5. `get-library-docs` fetches up-to-date documentation using that ID
6. The agent streams the response back with relevant code snippets and explanations
