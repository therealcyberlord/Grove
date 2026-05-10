"""PageIndex retrieval tools - navigate and read an already-indexed document."""
import asyncio
import json

from langchain_core.tools import tool
from clients.pageindex import get_pageindex_client


@tool
async def pageindex_get_document(doc_id: str) -> dict:
    """Get document metadata: name, description, type, and page count.

    Args:
        doc_id: Document ID of an already-indexed document.

    Returns:
        Dict with doc_name, doc_description, type, page_count, error (str | None).
    """
    try:
        return json.loads(get_pageindex_client().get_document(doc_id))
    except Exception as e:
        return {"error": str(e)}


@tool
async def pageindex_get_structure(doc_id: str) -> dict:
    """Get the document's hierarchical section tree.

    Each node includes title, start/end page numbers, and an LLM-generated summary.
    Use summaries to answer high-level questions without fetching pages. Use
    start/end indices to plan targeted page fetches for specific figures or tables.

    Args:
        doc_id: Document ID of an already-indexed document.

    Returns:
        Nested structure dict, or dict with error key on failure.
    """
    try:
        return json.loads(get_pageindex_client().get_document_structure(doc_id))
    except Exception as e:
        return {"error": str(e)}


@tool
async def pageindex_get_page_content(doc_id: str, pages: str) -> dict:
    """Get the text content of sections from an indexed document.

    For markdown documents (SEC filings), `pages` is a line number range derived from
    pageindex_get_structure node line_nums. To fetch a single section:
      start = that node's line_num
      end   = next sibling node's line_num − 1  (or document line_count if last section)
    Example: Risk Factors at line 120, next section (MD&A) at line 340 → pages="120-339".
    Never fetch ranges that span multiple top-level sections - fetch one targeted section
    per call.

    For PDF documents, `pages` is physical page numbers (1-indexed).

    Args:
        doc_id: Document ID of an already-indexed document.
        pages: Range string - '120-339' for a range, '3,8' for individual points,
               '12' for a single point.

    Returns:
        List of {page: int, content: str} dicts (one per section node in the range),
        or dict with error key on failure.
    """
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None, get_pageindex_client().get_page_content, doc_id, pages
        )
        return json.loads(result)
    except Exception as e:
        return {"error": str(e)}
