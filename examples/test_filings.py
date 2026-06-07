"""Quick test for the filings subagent - 10-K analysis via EDGAR and PageIndex."""
import asyncio
import logging
from agents.subagents.filings.agent import filings
from clients.langfuse import get_langfuse_callback

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

ticker = "CELH"
query = "Analyze the latest 10-K for Celsius Holdings. Cover key risk factors, management tone and guidance, audit opinion, and any red flags."

async def main():
    print(f"Ticker: {ticker}\nQuery: {query}\n{'='*60}\n")
    callbacks = [cb for cb in [get_langfuse_callback()] if cb is not None]
    result = await filings["runnable"].with_config({"callbacks": callbacks}).ainvoke(
        {"messages": [{"role": "user", "content": f"Ticker: {ticker}\n{query}"}]}
    )
    messages = result.get("messages", [])
    if messages:
        last = messages[-1]
        print(last.content if hasattr(last, "content") else str(last))
    else:
        print("No messages returned.")

asyncio.run(main())
