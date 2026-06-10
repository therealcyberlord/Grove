"""Unit tests for TUI display label mapping."""
from cli.labels import subagent_label, tool_label


def test_tool_label_returns_friendly_name_for_known_tools():
    assert tool_label("ticker_lookup") == "Looking up ticker"
    assert tool_label("tavily_news_search") == "Searching news"
    assert tool_label("tavily_finance_search") == "Searching financial news"
    assert tool_label("tavily_general_search") == "Searching web"
    assert tool_label("tavily_extract") == "Reading article"
    assert tool_label("yfinance_get_market_data") == "Fetching market data"
    assert tool_label("calculate") == "Calculating"
    assert tool_label("fetch_and_index_filing") == "Fetching SEC filing"
    assert tool_label("pageindex_get_document") == "Opening filing"
    assert tool_label("pageindex_get_structure") == "Reading filing structure"
    assert tool_label("pageindex_get_page_content") == "Reading filing section"


def test_tool_label_falls_back_to_raw_name_for_unknown_tools():
    assert tool_label("some_new_tool") == "some_new_tool"


def test_subagent_label_returns_friendly_name_for_known_subagents():
    assert subagent_label("news_macro") == "News & Sentiment"
    assert subagent_label("market_data") == "Market Data"
    assert subagent_label("filings") == "SEC Filings"


def test_subagent_label_falls_back_to_raw_name_for_unknown_subagents():
    assert subagent_label("unknown_agent") == "unknown_agent"
