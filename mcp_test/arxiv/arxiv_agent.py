"""ArXiv MCP Agent - Search and analyze academic papers via LangChain + MCP."""

import asyncio
import os
import sys

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    load_dotenv()

    # Path to the arxiv-mcp server script
    server_script = os.path.join(os.path.dirname(__file__), "arxiv-mcp", "src", "server.py")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env={**os.environ, "TRANSPORT": "stdio"},
    )

    print("Connecting to ArXiv MCP server...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await load_mcp_tools(session)
            print(f"Loaded {len(tools)} tools: {', '.join(t.name for t in tools)}")

            llm = ChatAnthropic(model="claude-sonnet-4-20250514")
            agent = create_agent(llm, tools)

            print("\nArXiv Agent ready. Type your query (or 'quit' to exit).\n")

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
                    response = await agent.ainvoke(
                        {"messages": [("user", user_input)]}
                    )
                    ai_message = response["messages"][-1]
                    print(f"\nAgent: {ai_message.content}\n")
                except Exception as e:
                    print(f"\nError: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
