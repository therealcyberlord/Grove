"""Quick test for the Grove orchestrator"""
import asyncio
import logging

from agents.orchestrator import orchestrator
from clients.langfuse import get_langfuse_callback

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

query = "Give me an in-depth analysis of META"

async def main():
    print(f"Query: {query}\n{'='*60}\n")
    callbacks = [cb for cb in [get_langfuse_callback()] if cb is not None]
    result = await orchestrator.with_config({"callbacks": callbacks}).ainvoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    messages = result.get("messages", [])
    if messages:
        last = messages[-1]
        print(last.content if hasattr(last, "content") else str(last))
    else:
        print("No messages returned.")


asyncio.run(main())
