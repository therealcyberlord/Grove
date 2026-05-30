"""Grove orchestrator - routes user queries to specialist subagents and synthesizes a final report."""
from deepagents import create_deep_agent

from agents.subagents.filings.agent import filings
from agents.subagents.market_data.agent import market_data
from agents.subagents.news_macro.agent import news_macro
from agents.system_prompt import SYSTEM_PROMPT
from agents.tools.yahoo_finance import ticker_lookup
from clients.llm import build_openrouter_client


orchestrator = create_deep_agent(
    model=build_openrouter_client(temperature=0.2),
    tools=[ticker_lookup],
    system_prompt=SYSTEM_PROMPT,
    subagents=[news_macro, market_data, filings],
    name="Grove",
)
