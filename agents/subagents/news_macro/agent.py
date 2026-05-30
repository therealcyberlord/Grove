"""News & Macro subagent - sentiment, events, and forward scenarios via Tavily."""
from deepagents import CompiledSubAgent
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware

from agents.middleware import SystemDateMiddleware, TavilyExtractSummarizer
from agents.subagents.news_macro.system_prompt import SYSTEM_PROMPT
from agents.tools.tavily import tavily_extract, tavily_finance_search, tavily_news_search
from clients.llm import build_openrouter_client

tools = [tavily_news_search, tavily_finance_search, tavily_extract]

agent = create_agent(
    model=build_openrouter_client(temperature=0.2),
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    middleware=[
        ModelRetryMiddleware(max_retries=3, backoff_factor=2.0, initial_delay=1.0),
        SystemDateMiddleware(),
        TavilyExtractSummarizer(
            model=build_openrouter_client(model="google/gemini-3.1-flash-lite-preview", temperature=0.2)
        ),
    ],
    name="news_macro_subagent",
)

news_macro: CompiledSubAgent = {
    "name": "news_macro",
    "description": (
        "Research recent news, sentiment, macro context, and forward scenarios for a stock ticker. "
        "Returns a self-contained markdown report with cited article URLs."
    ),
    "runnable": agent,
}
