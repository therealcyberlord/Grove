"""Human-readable label mapping for tools and subagents."""

_TOOL_LABELS: dict[str, str] = {
    "ticker_lookup": "Looking up ticker",
    "tavily_news_search": "Searching news",
    "tavily_finance_search": "Searching financial news",
    "tavily_general_search": "Searching web",
    "tavily_extract": "Reading article",
    "yfinance_get_market_data": "Fetching market data",
    "calculate": "Calculating",
    "fetch_and_index_filing": "Fetching SEC filing",
    "pageindex_get_document": "Opening filing",
    "pageindex_get_structure": "Reading filing structure",
    "pageindex_get_page_content": "Reading filing section",
}

_SUBAGENT_LABELS: dict[str, str] = {
    "news_macro": "News & Sentiment",
    "market_data": "Market Data",
    "filings": "SEC Filings",
}


def tool_label(name: str) -> str:
    """Return a human-readable label for a tool name.

    Falls back to the raw name if the tool is not in the mapping.
    """
    return _TOOL_LABELS.get(name, name)


def subagent_label(name: str) -> str:
    """Return a human-readable label for a subagent name.

    Falls back to the raw name if the subagent is not in the mapping.
    """
    return _SUBAGENT_LABELS.get(name, name)
