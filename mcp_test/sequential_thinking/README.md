# Sequential Thinking MCP Agent

An interactive agent that uses the [Sequential Thinking MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking) for step-by-step reasoning, powered by LangChain and Claude.

## Setup

### 1. Create and activate virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install langchain-anthropic langchain-mcp-adapters langchain python-dotenv mcp
```

### 3. Configure environment variables

Create a `.env` file:

```env
ANTHROPIC_API_KEY=your-api-key-here
```

### 4. Run the agent

```bash
python sequential_thinking_agent.py
```

## Test Examples

Once the agent is running, try these prompts:

### Example 1: Algorithm Design

```
You: Design a rate limiter for an API. Think through the trade-offs of different approaches.
```

Expected: The agent uses `sequential_thinking` to walk through token bucket, sliding window, and fixed window algorithms, comparing pros/cons before recommending an approach.

### Example 2: Debugging Strategy

```
You: A web app returns 200 OK but the page is blank. Walk me through how to debug this.
```

Expected: The agent breaks down the debugging process step by step - check network tab, inspect DOM, review console errors, verify API responses, check rendering logic.

### Example 3: System Architecture

```
You: Design a notification system that supports email, SMS, and push notifications with retry logic.
```

Expected: The agent reasons through component design, message queue choice, retry strategies, and failure handling in sequential steps.

### Example 4: Problem Decomposition

```
You: How would you migrate a monolithic app to microservices without downtime?
```

Expected: The agent sequentially thinks through strangler fig pattern, service boundaries, data migration, traffic routing, and rollback strategy.

### Example 5: Code Review Reasoning

```
You: What are the security concerns with accepting user-uploaded files in a web application?
```

Expected: The agent methodically works through file type validation, size limits, storage location, malware scanning, access control, and path traversal prevention.

## How It Works

The agent connects to the Sequential Thinking MCP server via stdio, which provides a `sequential_thinking` tool. When the LLM encounters complex problems, it uses this tool to break reasoning into numbered steps, allowing it to revise and branch its thinking before delivering a final answer.
