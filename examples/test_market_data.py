"""Quick test for the market_data subagent."""
import asyncio
from agents.subagents.market_data.agent import market_data

ticker = "CELH"
query = "Give me a full quantitative overview of Celsius Holdings."

async def main():
   
    print(f"Ticker: {ticker}\nQuery: {query}\n")
    result = await market_data.ainvoke({"ticker": ticker, "query": query})
    print(result)

asyncio.run(main())
