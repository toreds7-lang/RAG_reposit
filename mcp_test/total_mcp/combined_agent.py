"""Combined MCP Agent - context7 + sequential_thinking + filesystem 동적 결합 에이전트.

사용자 질문 상황에 따라 적절한 MCP 서버를 자동으로 선택하거나 조합합니다:
- 라이브러리/API 문서 질문  → context7 도구
- 복잡한 분석·추론 필요     → sequential_thinking 도구
- 파일 읽기/쓰기/탐색      → filesystem 도구
- 복합 질문                 → 여러 도구 자동 조합
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

SYSTEM_PROMPT = """You are a versatile AI assistant with access to three categories of MCP tools.
Dynamically select the right tool(s) based on the user's question.

## Tool Categories

### context7 tools  (prefix: context7__)
Use when the user asks about:
- How to use a specific library, framework, or API
- Documentation, function signatures, or usage examples for any package
- "How do I use X in Y library?", "What does function Z do?"
- Version-specific behavior of a software library

### sequential_thinking tools  (prefix: sequential_thinking__)
Use when the user asks about:
- Problems that require breaking down into multiple logical steps
- Planning, system design, or architecture decisions
- Debugging complex systems or reasoning through cause and effect
- Any question where step-by-step thinking yields a better answer
- Trade-off analysis, comparisons, or deep multi-angle analysis

### filesystem tools  (prefix: filesystem__)
Use when the user asks about:
- Reading, writing, listing, searching, or modifying files or directories
- Checking file contents, project structure, or local code
- Creating, deleting, or moving files
- Any task involving the local file system

## Combination Strategy
For complex questions, freely combine multiple tool types:
- "Analyze this codebase and explain how it uses React"
  → filesystem__ (read files) + context7__ (look up React docs)
- "Read my config file and plan a refactor"
  → filesystem__ (read) + sequential_thinking__ (plan)
- "Find all Python files and reason about their architecture"
  → filesystem__ (list/read) + sequential_thinking__ (analyze)
- "Read requirements.txt and find docs for each library"
  → filesystem__ (read) + context7__ (look up each package)

Always briefly state which tool(s) you are about to use and why, then proceed.
"""


async def main():
    load_dotenv()

    allowed_dirs = (
        [os.path.abspath(d) for d in sys.argv[1:]]
        if len(sys.argv) > 1
        else [os.getcwd()]
    )

    print("Connecting to 3 MCP servers (context7, sequential_thinking, filesystem)...")

    client = MultiServerMCPClient(
        {
            "context7": {
                "command": "npx",
                "args": ["-y", "@upstash/context7-mcp@latest"],
                "transport": "stdio",
            },
            "sequential_thinking": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
                "transport": "stdio",
            },
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"] + allowed_dirs,
                "transport": "stdio",
            },
        }
    )

    tools = await client.get_tools()

    # 로드된 도구를 서버별로 그룹화하여 출력
    tool_groups: dict[str, list[str]] = {}
    for tool in tools:
        prefix = tool.name.split("__")[0] if "__" in tool.name else "other"
        tool_groups.setdefault(prefix, []).append(tool.name)

    print(f"Loaded {len(tools)} tools across {len(tool_groups)} servers:")
    for server, names in tool_groups.items():
        print(f"  [{server}] {', '.join(names)}")

    llm = ChatAnthropic(model="claude-sonnet-4-20250514")
    agent = create_react_agent(llm, tools, prompt=SystemMessage(content=SYSTEM_PROMPT))

    print(f"\nCombined Agent ready (allowed dirs: {', '.join(allowed_dirs)})")
    print("Type your question (or 'quit' to exit).\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        try:
            print("\nAgent: ", end="", flush=True)
            async for chunk, metadata in agent.astream(
                {"messages": [("user", user_input)]},
                stream_mode="messages",
            ):
                if hasattr(chunk, "content") and chunk.content:
                    if isinstance(chunk.content, str):
                        print(chunk.content, end="", flush=True)
                    elif isinstance(chunk.content, list):
                        for block in chunk.content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    print(block["text"], end="", flush=True)
                                elif block.get("type") == "tool_use":
                                    print(f"\n[Tool: {block['name']}]", flush=True)
            print("\n")
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
