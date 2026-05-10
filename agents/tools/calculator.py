"""Safe math expression evaluator for derived financial metrics."""
import math as _math
from typing import Any

from langchain_core.tools import tool

_ALLOWED: dict[str, Any] = {k: v for k, v in _math.__dict__.items() if not k.startswith("_")}
_ALLOWED["abs"] = abs
_ALLOWED["round"] = round


@tool
def calculate(expression: str) -> dict[str, Any]:
    """Evaluate a mathematical expression for computing derived financial metrics.

    Use this for CAGR, ROIC, gross margin %, and other formulas where precision
    matters and large financial numbers (billions) are involved.

    Supports: +, -, *, /, ** (power), and math module functions (sqrt, log, abs, round).

    Args:
        expression: A Python math expression string, e.g.:
                    "((250e9 / 180e9) ** (1/2) - 1) * 100"  - 2-year revenue CAGR %
                    "45e9 * 0.79 / (800e9 - 120e9) * 100"   - ROIC %
                    "120e9 / 950e9 * 100"                    - gross margin %

    Returns:
        Dictionary with keys:
          - result (float | None): The computed value.
          - error (str | None): Error message if evaluation failed.
    """
    try:
        result = eval(expression, {"__builtins__": {}}, _ALLOWED)  # noqa: S307
        return {"result": float(result), "error": None}
    except Exception as exc:
        return {"result": None, "error": str(exc)}
