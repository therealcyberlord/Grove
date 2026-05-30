from dataclasses import dataclass
from typing import Literal

RoutingType = Literal["sentiment", "market_data", "filings", "deep_dive", "comparison"]
SubagentName = Literal["news_macro", "market_data", "filings"]

@dataclass
class EvalCase:
    name: str
    query: str
    routing_type: RoutingType
    expected_subagents: list[SubagentName]

@dataclass
class SubagentEvalCase:
    name: str
    subagent: SubagentName
    ticker: str
    query: str


eval_dataset: list[EvalCase] = [
    EvalCase(
        name="celh_sentiment",
        query="What is the current market sentiment for CELH?",
        routing_type="sentiment",
        expected_subagents=["news_macro"],
    ),
    EvalCase(
        name="aapl_sentiment",
        query="What is the sentiment on Apple stock right now?",
        routing_type="sentiment",
        expected_subagents=["news_macro"],
    ),
    EvalCase(
        name="google_name_resolution",
        query="What's the current sentiment on Google?",
        routing_type="sentiment",
        expected_subagents=["news_macro"],
    ),
    EvalCase(
        name="nvda_sentiment",
        query="What is the current sentiment around NVIDIA?",
        routing_type="sentiment",
        expected_subagents=["news_macro"],
    ),
    EvalCase(
        name="tsla_sentiment",
        query="What's the market sentiment on Tesla right now?",
        routing_type="sentiment",
        expected_subagents=["news_macro"],
    ),
    EvalCase(
        name="tsla_metrics",
        query="What are Tesla's key financial metrics and valuation multiples?",
        routing_type="market_data",
        expected_subagents=["market_data"],
    ),
    EvalCase(
        name="nvda_metrics",
        query="Give me NVIDIA's key financial metrics and valuation multiples.",
        routing_type="market_data",
        expected_subagents=["market_data"],
    ),
    EvalCase(
        name="aapl_metrics",
        query="What are Apple's current valuation multiples and profitability metrics?",
        routing_type="market_data",
        expected_subagents=["market_data"],
    ),
    EvalCase(
        name="msft_metrics",
        query="What are Microsoft's key financials — margins, cash flow, and valuation?",
        routing_type="market_data",
        expected_subagents=["market_data"],
    ),
    # Filings tickers overlap with deep_dive cases to share PageIndex cache within a run.
    EvalCase(
        name="celh_filing",
        query="What are the main risk factors in Celsius Holdings' latest 10-K?",
        routing_type="filings",
        expected_subagents=["filings"],
    ),
    EvalCase(
        name="mrna_filing",
        query="Summarize Moderna's latest 10-K: management tone, key risks, and any red flags.",
        routing_type="filings",
        expected_subagents=["filings"],
    ),
    EvalCase(
        name="rely_filing",
        query="What does Remitly's latest 10-K say about regulatory risks and competitive pressures?",
        routing_type="filings",
        expected_subagents=["filings"],
    ),
    EvalCase(
        name="celh_deep_dive",
        query="Give me a comprehensive analysis of Celsius Holdings.",
        routing_type="deep_dive",
        expected_subagents=["news_macro", "market_data", "filings"],
    ),
    EvalCase(
        name="mrna_deep_dive",
        query="Give me a full in-depth analysis of Moderna.",
        routing_type="deep_dive",
        expected_subagents=["news_macro", "market_data", "filings"],
    ),
    EvalCase(
        name="rely_deep_dive",
        query="Deep dive on Remitly - is it a buy right now?",
        routing_type="deep_dive",
        expected_subagents=["news_macro", "market_data", "filings"],
    ),
    EvalCase(
        name="googl_deep_dive",
        query="Full deep dive on Alphabet - financials, sentiment, and filing analysis.",
        routing_type="deep_dive",
        expected_subagents=["news_macro", "market_data", "filings"],
    ),
    EvalCase(
        name="nvda_amd_comparison",
        query="Compare NVDA vs AMD across valuation, growth, and sentiment",
        routing_type="comparison",
        expected_subagents=["news_macro", "market_data"],
    ),
    EvalCase(
        name="aapl_msft_comparison",
        query="Compare Apple vs Microsoft - which is the better investment right now?",
        routing_type="comparison",
        expected_subagents=["news_macro", "market_data"],
    ),
    EvalCase(
        name="tsla_rivn_comparison",
        query="Compare Tesla vs Rivian on growth, valuation, and market sentiment.",
        routing_type="comparison",
        expected_subagents=["news_macro", "market_data"],
    ),
    EvalCase(
        name="micron_name_resolution",
        query="What's the sentiment on Micron Technology?",
        routing_type="sentiment",
        expected_subagents=["news_macro"],
    ),
    # Earnings-framed query should route to news_macro only, not bleed into market_data.
    EvalCase(
        name="aapl_earnings_news",
        query="What happened at Apple's most recent earnings call?",
        routing_type="sentiment",
        expected_subagents=["news_macro"],
    ),
]

# Two cases per subagent so a single anomalous run doesn't skew results.
subagent_eval_dataset: list[SubagentEvalCase] = [
    SubagentEvalCase(
        name="subagent_news_macro_celh",
        subagent="news_macro",
        ticker="CELH",
        query="What is the current sentiment for CELH?",
    ),
    SubagentEvalCase(
        name="subagent_news_macro_nvda",
        subagent="news_macro",
        ticker="NVDA",
        query="What is the current sentiment for NVDA?",
    ),
    SubagentEvalCase(
        name="subagent_market_data_aapl",
        subagent="market_data",
        ticker="AAPL",
        query="Give me a full quantitative overview of Apple.",
    ),
    SubagentEvalCase(
        name="subagent_market_data_msft",
        subagent="market_data",
        ticker="MSFT",
        query="Give me a full quantitative overview of Microsoft.",
    ),
    SubagentEvalCase(
        name="subagent_filings_googl",
        subagent="filings",
        ticker="GOOGL",
        query="Analyze the latest 10-K for Alphabet. Cover key risk factors, management tone, and any red flags.",
    ),
    SubagentEvalCase(
        name="subagent_filings_mrna",
        subagent="filings",
        ticker="MRNA",
        query="Analyze the latest 10-K for Moderna. Cover key risk factors, management tone, and any red flags.",
    ),
]
