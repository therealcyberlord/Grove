"""Quick test for the Grove orchestrator"""
import asyncio
import logging

from agents.orchestrator import orchestrator
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

query = "What is the sentiment of Celsius?"

async def main():
    print(f"Query: {query}\n{'='*60}\n")
    result = await orchestrator.with_config({"callbacks": [LangfuseCallbackHandler()]}).ainvoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    messages = result.get("messages", [])
    if messages:
        last = messages[-1]
        print(last.content if hasattr(last, "content") else str(last))
    else:
        print("No messages returned.")


asyncio.run(main())
