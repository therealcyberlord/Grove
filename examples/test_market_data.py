"""Quick test for the market_data subagent."""
import asyncio
from agents.subagents.market_data.agent import market_data
from clients.langfuse import get_langfuse_callback

ticker = "CELH"
query = "Give me a full quantitative overview of Celsius Holdings."

async def main():
    print(f"Ticker: {ticker}\nQuery: {query}\n")
    callbacks = [cb for cb in [get_langfuse_callback()] if cb is not None]
    result = await market_data["runnable"].with_config({"callbacks": callbacks}).ainvoke(
        {"messages": [{"role": "user", "content": f"Ticker: {ticker}\n{query}"}]}
    )
    messages = result.get("messages", [])
    if messages:
        last = messages[-1]
        print(last.content if hasattr(last, "content") else str(last))
    else:
        print("No messages returned.")

asyncio.run(main())
