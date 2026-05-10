"""Quick test for the Grove orchestrator - full in-depth report."""
from agents.orchestrator import agent
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

query = "Give me an in-depth analysis of Moderna and whether it is a buy"

async def main():
    print(f"Query: {query}\n{'='*60}\n")
    result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
    messages = result.get("messages", [])
    if messages:
        last = messages[-1]
        print(last.content if hasattr(last, "content") else str(last))
    else:
        print("No messages returned.")


asyncio.run(main())
