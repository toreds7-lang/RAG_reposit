"""Sequential Thinking MCP Agent - Step-by-step reasoning via LangChain + MCP."""

import asyncio
import sys

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    load_dotenv()

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-sequential-thinking"],
    )

    print("Connecting to Sequential Thinking MCP server...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await load_mcp_tools(session)
            print(f"Loaded {len(tools)} tools: {', '.join(t.name for t in tools)}")

            llm = ChatAnthropic(model="claude-sonnet-4-20250514")
            agent = create_agent(llm, tools)

            print("\nSequential Thinking Agent ready. Type your instructions (or 'quit' to exit).\n")

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
