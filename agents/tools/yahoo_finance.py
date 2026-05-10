"""Yahoo Finance market data tools."""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf
from langchain.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="yfinance")


class MarketData(BaseModel):
    # Identity
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None

    # Price
    current_price: float | None = None

    # Valuation
    market_cap: float | None = None
    enterprise_value: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    ev_ebitda: float | None = None
    price_to_book: float | None = None
    price_to_sales: float | None = None

    # Balance sheet
    total_debt: float | None = None
    total_cash: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None

    # Margins
    gross_margins: float | None = None
    operating_margins: float | None = None
    profit_margins: float | None = None

    # Growth (TTM = trailing twelve months vs. prior TTM - not full fiscal year)
    revenue_growth_ttm: float | None = None
    earnings_growth_ttm: float | None = None

    # Cash flow (FCF derived as operating_cash_flow + capex, where capex is negative)
    free_cash_flow: float | None = None
    operating_cash_flow: float | None = None
    buyback_by_year: dict[str, float] | None = Field(
    default=None,
    description="Annual buybacks keyed by year string e.g. {'2024': 5.2e9, '2023': 3.1e9}",
)

    # Returns & other
    return_on_equity: float | None = None
    return_on_assets: float | None = None
    shares_outstanding: float | None = None
    held_percent_insiders: float | None = None
    beta: float | None = None

    # Dividends (TTM; None for non-dividend payers)
    dividend_yield: float | None = None
    payout_ratio: float | None = None

    # Metadata
    fundamentals_period: str | None = None  # ISO date of most recent reported quarter (mostRecentQuarter)
    error: str | None = None

def _to_float(val) -> float | None:
    if val is None:
        return None
    return float(val)


def _derive_fcf(ticker: yf.Ticker) -> float | None:
    """Compute FCF = operating cash flow + capital expenditure (capex stored as negative)."""
    try:
        cf = ticker.cashflow
        if cf is None or cf.empty:
            return None
        most_recent = cf.iloc[:, 0]
        op_cf = None
        capex = None
        for label in most_recent.index:
            label_lower = str(label).lower()
            if "operating" in label_lower and "cash" in label_lower:
                op_cf = _to_float(most_recent[label])
            elif "capital expenditure" in label_lower:
                capex = _to_float(most_recent[label])
        if op_cf is not None and capex is not None:
            return op_cf + capex  # capex is already negative
    except Exception:
        logger.debug("FCF derivation failed for %s", ticker.ticker, exc_info=True)
    return None


def _derive_roe_roa(ticker: yf.Ticker) -> tuple[float | None, float | None]:
    """Compute ROE and ROA from statements using the same net income basis.

    yfinance's returnOnAssets uses EBITDA for some companies and net income for others,
    making ROE/ROA comparisons unreliable. Deriving both from annual statements ensures
    a consistent net income basis: ROE = net income / equity, ROA = net income / total assets.
    """
    try:
        income = ticker.financials
        balance = ticker.balance_sheet
        if income is None or income.empty or balance is None or balance.empty:
            return None, None
        net_income = None
        equity = None
        total_assets = None
        for label in income.index:
            if "net income" in str(label).lower() and "common" not in str(label).lower():
                val = _to_float(income.iloc[:, 0][label])
                if val is not None:
                    net_income = val
                    break
        for label in balance.index:
            label_lower = str(label).lower()
            if "stockholders" in label_lower and "equity" in label_lower:
                val = _to_float(balance.iloc[:, 0][label])
                if val is not None:
                    equity = val
            if "total assets" in label_lower:
                val = _to_float(balance.iloc[:, 0][label])
                if val is not None:
                    total_assets = val
        roe = net_income / equity if net_income is not None and equity else None
        roa = net_income / total_assets if net_income is not None and total_assets else None
        return roe, roa
    except Exception:
        logger.debug("ROE/ROA derivation failed for %s", ticker.ticker, exc_info=True)
    return None, None


def _get_buyback_by_year(ticker: yf.Ticker) -> dict[str, float] | None:
    try:
        cf = ticker.cashflow
        if cf is None or cf.empty or "Repurchase Of Capital Stock" not in cf.index:
            return None
        row = cf.loc["Repurchase Of Capital Stock"].sort_index(ascending=False)
        result = {}
        for date, val in row.items():
            if pd.notna(val):
                result[str(date.year)] = abs(float(val))
        return result or None
    except Exception:
        logger.debug("Failed to fetch buyback data for %s", ticker.ticker, exc_info=True)
        return None


def _fetch_yfinance_sync(ticker: str) -> MarketData:
    try:
        yticker = yf.Ticker(ticker)
        info: dict[str, Any] = yticker.info or {}

        def _f(key: str) -> float | None:
            return _to_float(info.get(key))

        derived_fcf = _derive_fcf(yticker)
        derived_roe, derived_roa = _derive_roe_roa(yticker)

        mrq_ts = info.get("mostRecentQuarter")
        fundamentals_as_of = (
            datetime.fromtimestamp(mrq_ts, tz=timezone.utc).strftime("%Y-%m-%d")
            if mrq_ts
            else None
        )

        return MarketData(
            company_name=info.get("longName") or info.get("shortName"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            current_price=_f("currentPrice") or _f("regularMarketPrice"),
            market_cap=_f("marketCap"),
            enterprise_value=_f("enterpriseValue"),
            trailing_pe=_f("trailingPE"),
            forward_pe=_f("forwardPE"),
            ev_ebitda=_f("enterpriseToEbitda"),
            price_to_book=_f("priceToBook"),
            price_to_sales=_f("priceToSalesTrailing12Months"),
            total_debt=_f("totalDebt"),
            total_cash=_f("totalCash"),
            debt_to_equity=_f("debtToEquity"),
            current_ratio=_f("currentRatio"),
            gross_margins=_f("grossMargins"),
            operating_margins=_f("operatingMargins"),
            profit_margins=_f("profitMargins"),
            revenue_growth_ttm=_f("revenueGrowth"),
            earnings_growth_ttm=_f("earningsGrowth"),
            free_cash_flow=derived_fcf if derived_fcf is not None else _f("freeCashflow"),
            operating_cash_flow=_f("operatingCashflow"),
            return_on_equity=derived_roe if derived_roe is not None else _f("returnOnEquity"),
            return_on_assets=derived_roa if derived_roa is not None else _f("returnOnAssets"),
            shares_outstanding=_f("sharesOutstanding"),
            held_percent_insiders=_f("heldPercentInsiders"),
            beta=_f("beta"),
            buyback_by_year=_get_buyback_by_year(yticker),
            dividend_yield=_f("dividendYield"),
            payout_ratio=_f("payoutRatio"),
            fundamentals_period=fundamentals_as_of,
        )
    except Exception as exc:
        logger.warning("yfinance fetch failed for %s: %s", ticker, exc, exc_info=True)
        return MarketData(error=str(exc))


@tool
async def yfinance_get_market_data(ticker: str) -> dict[str, Any]:
    """Fetch current market data and valuation multiples from Yahoo Finance.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").

    Returns:
        Serialized MarketData. All numeric values may be None if unavailable.
        Check the `error` key for any fetch failures.
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_EXECUTOR, _fetch_yfinance_sync, ticker)
    return result.model_dump()


def _lookup_ticker_sync(company_name: str) -> list[dict]:
    results = yf.Search(company_name, max_results=8, enable_fuzzy_query=True).quotes
    return [
        {
            "ticker": r["symbol"],
            "name": r.get("longname") or r.get("shortname", ""),
            "exchange": r.get("exchDisp", r.get("exchange", "")),
            "type": r.get("quoteType", ""),
        }
        for r in results
        if r.get("quoteType") == "EQUITY"
    ]


@tool
async def ticker_lookup(company_name: str) -> list[dict]:
    """Resolve a company name to its stock ticker symbol and exchange.

    Use this whenever the user provides a company name without a ticker, or when
    the correct ticker is uncertain (e.g. recent IPOs, spin-offs, misspelled names).

    Args:
        company_name: Company name or partial name (e.g. "Palantir", "CoreWeave", "Arm Holdings").

    Returns:
        List of up to 8 matching equities, each with ticker, name, and exchange.
        Use the first result unless the query clearly targets a different match.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_EXECUTOR, _lookup_ticker_sync, company_name)


if __name__ == "__main__":
    print(asyncio.run(yfinance_get_market_data.ainvoke({"ticker": "CELH"})))