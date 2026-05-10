"""Quick test for the news_macro subagent."""
import asyncio
from agents.subagents.news_macro.agent import news_macro

query = "What is the current sentiment for CELH (Celsius Holdings)?"

async def main():
    print(f"Query: {query}\n")
    result = await news_macro.ainvoke({"request": {"query": query, "model": "deepseek/deepseek-v4-pro"}})
    print(result)

asyncio.run(main())
