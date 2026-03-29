"""MCP Bash Agent - Execute bash commands via LangChain + MCP."""

import asyncio
import os
import sys

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Path to the cloned mcp-bash server.py
MCP_BASH_SERVER = os.path.join(os.path.dirname(__file__), "mcp-bash", "server.py")


async def main():
    load_dotenv()

    if not os.path.exists(MCP_BASH_SERVER):
        print(f"Error: {MCP_BASH_SERVER} not found.")
        print("Clone the repo first: git clone https://github.com/patrickomatik/mcp-bash.git")
        sys.exit(1)

    server_params = StdioServerParameters(
        command="uv",
        args=[
            "run",
            "--with", "mcp[cli]",
            "mcp", "run",
            MCP_BASH_SERVER,
        ],
    )

    print("Connecting to MCP Bash server...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await load_mcp_tools(session)
            print(f"Loaded {len(tools)} tools: {', '.join(t.name for t in tools)}")

            llm = ChatAnthropic(model="claude-sonnet-4-20250514")
            agent = create_react_agent(llm, tools)

            print("\nMCP Bash Agent ready. Type your instructions (or 'quit' to exit).\n")

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
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        print(block["text"], end="", flush=True)
                    print("\n")
                except Exception as e:
                    print(f"\nError: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
