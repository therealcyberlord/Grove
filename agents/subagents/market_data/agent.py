"""Market data subagent - quantitative metrics via Yahoo Finance."""
from deepagents import CompiledSubAgent
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware

from agents.middleware.system_date import SystemDateMiddleware
from agents.subagents.market_data.system_prompt import SYSTEM_PROMPT
from agents.tools.calculator import calculate
from agents.tools.yahoo_finance import yfinance_get_market_data
from clients.llm import build_openrouter_client

_tools = [yfinance_get_market_data, calculate]

_agent = create_agent(
    model=build_openrouter_client(temperature=0.1),
    tools=_tools,
    system_prompt=SYSTEM_PROMPT,
    middleware=[
        SystemDateMiddleware(),
        ModelRetryMiddleware(max_retries=3, backoff_factor=2.0, initial_delay=1.0),
    ],
)

market_data: CompiledSubAgent = {
    "name": "market_data",
    "description": (
        "Retrieve and analyze quantitative market data for a stock ticker via Yahoo Finance - "
        "valuation multiples, margins, cash flows, balance sheet, and capital allocation. "
        "Returns a formatted markdown report."
    ),
    "runnable": _agent,
}
