"""Quick test for the news_macro subagent."""
import asyncio
from agents.subagents.news_macro.agent import news_macro

query = "What is the current sentiment for CELH (Celsius Holdings)?"

async def main():
    print(f"Query: {query}\n")
    result = await news_macro["runnable"].ainvoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    messages = result.get("messages", [])
    if messages:
        last = messages[-1]
        print(last.content if hasattr(last, "content") else str(last))
    else:
        print("No messages returned.")

asyncio.run(main())
