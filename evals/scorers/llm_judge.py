"""LLM-as-judge evaluators using Gemini Flash Lite and structured output."""
import logging
from datetime import date
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langfuse.experiment import Evaluation
from pydantic import BaseModel, Field

from clients.llm import build_openrouter_client

logger = logging.getLogger(__name__)

_JUDGE_MODEL = "google/gemini-3.1-flash-lite-preview"


class JudgeOutput(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reason: str


@lru_cache(maxsize=1)
def _get_judge_model():
    return build_openrouter_client(model=_JUDGE_MODEL, temperature=0.1).with_structured_output(JudgeOutput)


def _evaluation(name: str, result: JudgeOutput) -> Evaluation:
    return Evaluation(name=name, value=round(result.score, 2), comment=result.reason)


_HELPFULNESS_SYSTEM = """\
You are an evaluator for a financial research assistant. Today's date is {today}. Score the report on how well it answers the user query.

Rubric:
1.0 - Fully addresses the query with specific data for the requested ticker(s). All aspects asked for are covered.
0.75 - Mostly answers, with minor gaps (one aspect missing or slightly off-focus).
0.5 - Partially answers: right topic but missing substantial data, or not all tickers covered in a comparison query.
0.25 - Barely answers: generic content, wrong focus, or the core ask is absent.
0.0 - Does not answer the question, or is about the wrong company entirely."""

_HELPFULNESS_USER = """\
Query: {query}

Report:
{report}"""


async def score_helpfulness(*, input, output, **_) -> Evaluation:
    query = input.get("query", "")
    report = output.get("report", "")

    try:
        result = await _get_judge_model().ainvoke([
            SystemMessage(content=_HELPFULNESS_SYSTEM.format(today=date.today().isoformat())),
            HumanMessage(content=_HELPFULNESS_USER.format(query=query, report=report)),
        ])
        return _evaluation("helpfulness", result)
    except Exception:
        logger.warning("llm_judge: helpfulness scoring failed", exc_info=True)
        return Evaluation(name="helpfulness", value=0.0, comment="scoring_error")


_SUBAGENT_RUBRICS = {
    "news_macro": (
        "Covers: recent news events, an overall sentiment stance (bullish/bearish/neutral), "
        "key catalysts or risks, and at least one cited URL or source."
    ),
    "market_data": (
        "Covers: valuation metrics (P/E, P/S, EV/EBITDA, or similar), revenue or earnings figures, "
        "key margin data, and cites Yahoo Finance as source."
    ),
    "filings": (
        "Covers: key risk factors from the 10-K, management discussion or strategy signals, "
        "any red flags or concerns, and cites SEC filing sections as source."
    ),
}

_SUBAGENT_SYSTEM = """\
You are an evaluator for a financial research subagent. Today's date is {today}. Score the response based on whether it covers the required rubric for the given ticker.

Subagent: {subagent}
Ticker: {ticker}
Rubric: {rubric}

Scoring:
1.0 - Fully covers all rubric areas with specific data for {ticker}.
0.5 - Partially covers the rubric, or the data is present but too generic (not ticker-specific).
0.0 - Misses key rubric areas, is about the wrong company, or is trivially short."""


async def score_subagent_quality(*, input, output, **_) -> Evaluation:
    subagent = input.get("subagent", "")
    ticker = input.get("ticker", "")
    report = output.get("report", "")
    rubric = _SUBAGENT_RUBRICS.get(subagent, "Produces a relevant, sourced financial analysis for the ticker.")

    try:
        result = await _get_judge_model().ainvoke([
            SystemMessage(content=_SUBAGENT_SYSTEM.format(today=date.today().isoformat(), subagent=subagent, ticker=ticker, rubric=rubric)),
            HumanMessage(content=f"Response:\n{report}"),
        ])
        return _evaluation("subagent_quality", result)
    except Exception:
        logger.warning("llm_judge: subagent_quality scoring failed", exc_info=True)
        return Evaluation(name="subagent_quality", value=0.0, comment="scoring_error")
