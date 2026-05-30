"""Rule-based check: every URL in the report must have come from a tool result."""
import re

from langfuse.experiment import Evaluation

# Also imported by experiments.py so both sides use identical parsing and false fabrication flags are impossible.
URL_RE = re.compile(r"https?://[^\s\"')\]><]+")


def score_no_fabricated_urls(report: str, tool_urls: list[str]) -> Evaluation:
    report_urls = set(URL_RE.findall(report))
    fabricated = report_urls - set(tool_urls)
    if fabricated:
        return Evaluation(
            name="no_fabricated_urls",
            value=0.0,
            comment=f"fabricated: {sorted(fabricated)}",
        )
    return Evaluation(
        name="no_fabricated_urls",
        value=1.0,
        comment=f"all {len(report_urls)} URL(s) verified" if report_urls else "no URLs in report",
    )
