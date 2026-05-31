"""Checks which subagents ran by inspecting tool names captured during graph execution."""
from langfuse.experiment import Evaluation

SUBAGENT_TOOLS: dict[str, set[str]] = {
    "news_macro": {"tavily_news_search", "tavily_finance_search", "tavily_extract"},
    "market_data": {"yfinance_get_market_data", "calculate"},
    "filings": {"fetch_and_index_filing", "pageindex_get_structure", "pageindex_get_page_content"},
}


def score_routing(tool_names: list[str], expected: list[str]) -> Evaluation:
    # Jaccard similarity; partial credit for partial matches, penalizes over-routing.
    tool_set = set(tool_names)
    detected = {
        subagent
        for subagent, tools in SUBAGENT_TOOLS.items()
        if tools & tool_set
    }
    expected_set = set(expected)
    union = detected | expected_set
    index = len(detected & expected_set) / len(union) if union else 1.0

    parts = [f"expected={sorted(expected_set)}", f"detected={sorted(detected)}"]
    if detected != expected_set:
        if expected_set - detected:
            parts.append(f"missing={sorted(expected_set - detected)}")
        if detected - expected_set:
            parts.append(f"extra={sorted(detected - expected_set)}")

    return Evaluation(
        name="subagent_routing",
        value=round(index, 2),
        comment=" | ".join(parts),
    )
