"""Quick test for the filings subagent - 10-K analysis via EDGAR and PageIndex."""
import asyncio
import logging
from agents.subagents.filings.agent import filings

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

ticker = "CELH"
query = "Analyze the latest 10-K for Celsius Holdings. Cover key risk factors, management tone and guidance, audit opinion, and any red flags."

async def main():
    print(f"Ticker: {ticker}\nQuery: {query}\n{'='*60}\n")
    result = await filings.ainvoke({"ticker": ticker, "query": query})
    print(result)

asyncio.run(main())
