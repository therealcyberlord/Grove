"""Filings subagent - SEC filing analysis via EDGAR and PageIndex."""
import asyncio
import logging
from pathlib import Path

from deepagents import CompiledSubAgent
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware, ToolCallLimitMiddleware
from langchain_core.tools import tool

from agents.subagents.filings.system_prompt import SYSTEM_PROMPT
from agents.tools.pageindex import pageindex_get_page_content, pageindex_get_structure
from clients.llm import build_openrouter_client
from clients.pageindex import get_pageindex_client

logger = logging.getLogger(__name__)

_DOCUMENTS_DIR = Path(__file__).parent.parent.parent.parent / "documents"


def _do_fetch_and_index(ticker: str) -> tuple[str, str]:
    """Returns (doc_id, period_of_report) for the latest 10-K."""
    from edgar import Company, set_identity

    from clients.config import settings
    set_identity(settings.edgar_identity)

    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest()
    if filing is None:
        raise ValueError(f"No 10-K found for {ticker}")

    period = filing.period_of_report
    filename = f"{ticker}_10-K_{period}.md"

    client = get_pageindex_client()
    existing_id = next(
        (did for did, doc in client.documents.items() if doc.get("doc_name") == filename),
        None,
    )
    if existing_id:
        logger.info("filings: cache hit %s -> %s", filename, existing_id)
        return existing_id, period

    logger.info("filings: fetching %s 10-K via EDGAR (period=%s)", ticker, period)
    md_content = filing.markdown()

    _DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = _DOCUMENTS_DIR / filename
    dest.write_text(md_content, encoding="utf-8")
    logger.info("filings: saved %s (%d chars)", filename, len(md_content))

    doc_id = client.index(str(dest))
    logger.info("filings: indexed %s -> doc_id=%s", filename, doc_id)
    return doc_id, period


@tool
async def fetch_and_index_filing(ticker: str) -> dict:
    """Fetch the latest 10-K from EDGAR, convert to markdown, and index with PageIndex.

    Call this first before using any pageindex tools. Returns a doc_id to pass to
    pageindex_get_structure and pageindex_get_page_content, and a period (YYYY-MM-DD)
    indicating the fiscal year end date of the filing.

    Args:
        ticker: Stock ticker symbol (e.g. "CELH").

    Returns:
        dict with "doc_id" (str), "period" (str), and "error" (str | None).
    """
    try:
        loop = asyncio.get_running_loop()
        doc_id, period = await loop.run_in_executor(None, _do_fetch_and_index, ticker)
        return {"doc_id": doc_id, "period": period, "error": None}
    except Exception as exc:
        logger.error("fetch_and_index_filing failed for %s: %s", ticker, exc)
        return {"doc_id": None, "period": None, "error": str(exc)}


tools = [fetch_and_index_filing, pageindex_get_structure, pageindex_get_page_content]

agent = create_agent(
    model=build_openrouter_client(temperature=0.1),
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    middleware=[
        ModelRetryMiddleware(max_retries=3, backoff_factor=2.0, initial_delay=1.0),
        ToolCallLimitMiddleware(tool_name="pageindex_get_page_content", run_limit=5, exit_behavior="continue"),
    ],
    name="filings_subagent",
)

filings: CompiledSubAgent = {
    "name": "filings",
    "description": (
        "Fetch and qualitatively analyze the latest 10-K annual report for a stock ticker "
        "via EDGAR and PageIndex. Covers risk factors, management tone, guidance language, "
        "audit opinions, and governance red flags."
    ),
    "runnable": agent,
}
