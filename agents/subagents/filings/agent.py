"""Filings subagent - SEC filing analysis via EDGAR and PageIndex."""
import asyncio
import logging
import tempfile
from datetime import date
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

_STALE_AFTER_DAYS = 365


def _do_fetch_and_index(ticker: str) -> tuple[str, str]:
    """Returns (doc_id, period_of_report) for the latest 10-K."""
    from edgar import Company, set_identity

    from clients.config import settings
    from clients.database import get_db_session
    from models.db import Filing, PageIndexRecord

    set_identity(settings.edgar_identity)

    # DB-first cache check — no EDGAR call until we know we have a cache miss.
    # Two separate sessions are intentional: the first closes before any blocking
    # network I/O (EDGAR fetch, S3 upload) so it doesn't hold a DB connection idle.
    with get_db_session() as session:
        db_filing = (
            session.query(Filing)
            .filter_by(ticker=ticker, form_type="10-K")
            .order_by(Filing.period.desc())
            .first()
        )
        if db_filing is not None:
            age = (date.today() - db_filing.period).days
            if age <= _STALE_AFTER_DAYS:
                pi_row = session.query(PageIndexRecord).filter_by(filing_id=db_filing.id).first()
                if pi_row is not None:
                    logger.info(
                        "filings: DB cache hit %s (period=%s, age=%d days)",
                        ticker, db_filing.period, age,
                    )
                    client = get_pageindex_client()
                    if pi_row.doc_id not in client.documents:
                        client._hydrate_single_from_db(pi_row.doc_id)
                    return pi_row.doc_id, str(db_filing.period)
            else:
                logger.info(
                    "filings: DB cache stale for %s (period=%s, age=%d days), re-fetching",
                    ticker, db_filing.period, age,
                )

    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest()
    if filing is None:
        raise ValueError(f"No 10-K found for {ticker}")

    period = filing.period_of_report
    filename = f"{ticker}_10-K_{period}.md"

    logger.info("filings: fetching %s 10-K via EDGAR (period=%s)", ticker, period)
    md_content = filing.markdown()

    from clients.storage import upload_filing
    s3_key = upload_filing(ticker, filename, md_content)
    period_date = date.fromisoformat(str(period))
    
    with get_db_session() as session:
        db_filing = (
            session.query(Filing)
            .filter_by(ticker=ticker, form_type="10-K", period=period_date)
            .first()
        )
        if db_filing is not None:
            db_filing.doc_name = filename
            db_filing.content_s3_key = s3_key
        else:
            session.add(Filing(
                ticker=ticker,
                form_type="10-K",
                period=period_date,
                fiscal_year=period_date.year,
                fiscal_quarter=4,
                doc_name=filename,
                content_s3_key=s3_key,
            ))

    # Write to a temp file for PageIndex (content lives in inline structure after indexing).
    # Use the canonical filename so PageIndex derives doc_name from it (it strips the
    # extension off the basename) - this is what _persist_index_to_db matches against
    # Filing.doc_name to resolve the filing_id FK.
    client = get_pageindex_client()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = str(Path(tmp_dir) / filename)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        doc_id = client.index(tmp_path)
    logger.info("filings: indexed %s -> doc_id=%s", filename, doc_id)
    return doc_id, str(period)


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
