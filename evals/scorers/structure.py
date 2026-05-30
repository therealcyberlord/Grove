"""Checks required and forbidden section headers in the final response."""
import re

from langfuse.experiment import Evaluation

_HEADER_RE = r"#{1,3}\s[^\n]*%s"


def score_structure(
    response: str,
    required_sections: list[str],
    forbidden_sections: list[str],
) -> Evaluation:
    # Matches as markdown headers (##/###), not raw substrings, to avoid false positives in quoted text.
    checks: list[tuple[str, bool]] = []

    for section in required_sections:
        found = bool(re.search(_HEADER_RE % re.escape(section), response, re.IGNORECASE))
        checks.append((f"section '{section}'", found))

    for section in forbidden_sections:
        found = bool(re.search(_HEADER_RE % re.escape(section), response, re.IGNORECASE))
        checks.append((f"no section '{section}'", not found))

    if not checks:
        return Evaluation(name="report_structure", value=1.0, comment="no checks defined")

    passed = sum(1 for _, ok in checks if ok)
    score = passed / len(checks)
    detail = " | ".join(f"{'pass' if ok else 'fail'} {label}" for label, ok in checks)
    return Evaluation(name="report_structure", value=score, comment=detail)
