"""Tavily search and extract tools - shared across all subagents."""
from typing import Optional

from langchain_core.tools import tool

from clients.tavily import get_tavily_client


@tool
async def tavily_news_search(
    query: str,
    days: int = 30,
    max_results: int = 10,
) -> dict:
    """Search recent news articles for financial and market events.

    Args:
        query: Search query string (e.g. "Apple earnings Q1 2026" or "semiconductor sector tariffs").
        days: Number of past days to cover. Use 30 for recent news, 90 for quarter-level view.
        max_results: Maximum number of results to return (1–20).

    Returns:
        Tavily search response dict with keys: query, results, answer (optional).
        Each result contains: title, url, content, score, published_date.
    """
    client = get_tavily_client()
    return await client.search(
        query=query,
        topic="news",
        search_depth="advanced",
        days=days,
        max_results=max_results,
        include_answer=True,
    )


@tool
async def tavily_finance_search(
    query: str,
    days: int = 30,
    max_results: int = 10,
) -> dict:
    """Search financial data sources for analyst commentary, market data, and peer benchmarks.

    Args:
        query: Search query string (e.g. "NVDA EV/EBITDA peer comparison semiconductor 2026").
        days: Number of past days to cover.
        max_results: Maximum number of results to return (1–20).

    Returns:
        Tavily search response dict with keys: query, results, answer (optional).
        Each result contains: title, url, content, score, published_date.
    """
    client = get_tavily_client()
    return await client.search(
        query=query,
        topic="finance",
        search_depth="advanced",
        days=days,
        max_results=max_results,
        include_answer=True,
    )


@tool
async def tavily_general_search(
    query: str,
    days: int = 90,
    max_results: int = 8,
) -> dict:
    """Search the general web for regulatory filings, government policy, or niche sources.

    Use this for SEC filings, government policy announcements, and industry reports not
    captured by news or finance topic searches.

    Args:
        query: Search query string (e.g. "SEC investigation fintech companies 2026").
        days: Number of past days to cover.
        max_results: Maximum number of results to return (1–20).

    Returns:
        Tavily search response dict with keys: query, results, answer (optional).
        Each result contains: title, url, content, score, published_date.
    """
    client = get_tavily_client()
    return await client.search(
        query=query,
        topic="general",
        search_depth="advanced",
        days=days,
        max_results=max_results,
        include_answer=False,
    )


@tool
async def tavily_extract(
    urls: list[str],
    query: Optional[str] = None,
) -> dict:
    """Extract full article or page content from a list of URLs.

    Use this after a search to retrieve the complete text of the most relevant
    articles for deeper analysis.

    Args:
        urls: List of URLs to extract content from (max 5 recommended per call).
        query: Optional query string to focus extraction on relevant content chunks.

    Returns:
        Tavily extract response dict with key 'results', each item containing:
        url, raw_content, and optionally images.
    """
    client = get_tavily_client()
    return await client.extract(
        urls=urls,
        extract_depth="advanced",
        query=query,
    )
