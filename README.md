# Grove

<img src="Grove.png" width="280" alt="Grove" />

<sub>Image generated using Google Gemini Nano Banana</sub>

**The Analyst's Workbench.** Ask a question about any stock and Grove routes it to specialist AI subagents, then synthesizes a sourced markdown report with an investment thesis.

---

## What It Does

| Query type | Example | Subagents called |
|---|---|---|
| Sentiment | `"What's the sentiment on CELH?"` | `news_macro` |
| Market data | `"Give me NVDA's financials"` | `market_data` |
| Deep dive | `"Give me an in-depth analysis of AAPL"` | all three |
| Comparison | `"Compare AAPL vs MSFT"` | all three, per ticker |

Every report includes inline citations. URLs are sourced exclusively from tool results, never fabricated.

## Architecture

```
user query
  ↓
orchestrator: decides subagents + tickers
  ├─ news_macro(ticker)   → sentiment, events, macro context
  ├─ market_data(ticker)  → valuation, margins, cash flows, balance sheet
  └─ filings(ticker)      → 10-K risk factors, MD&A, audit opinion
  ↓
synthesized markdown report with investment thesis and sources
```

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | DeepSeek V4 Pro via OpenRouter; Gemini Flash Lite (summarization) |
| Orchestration | DeepAgents (orchestrator-subagent pattern) |
| Search | Tavily (news, finance, extract) |
| Market data | yfinance |
| SEC filings | edgartools + PageIndex |
| Observability | Langfuse |
| Runtime | Python 3.12+, uv |

## Setup

**1. Clone and install**

```bash
git clone https://github.com/therealcyberlord/Grove
cd backend
uv sync
```

**2. Clone PageIndex** (local library, not on PyPI)

```bash
git clone https://github.com/VectifyAI/PageIndex lib/PageIndex
```

**3. Configure environment variables.** Create a `.env` in the project root:

```
OPENROUTER_API_KEY=         # Required: DeepSeek and Gemini via OpenRouter
TAVILY_API_KEY=             # Required: all search tools
LANGFUSE_PUBLIC_KEY=        # Required: observability
LANGFUSE_SECRET_KEY=        # Required: observability
LANGFUSE_BASE_URL=          # Required: e.g. https://us.cloud.langfuse.com
ANTHROPIC_API_KEY=          # Optional: Claude API (not used by default agents)
EDGAR_IDENTITY=             # Required: SEC EDGAR User-Agent
```

## Running

```bash
# Full orchestrator (routes automatically based on query)
uv run python -m examples.test_orchestrator

# Individual subagents
uv run python -m examples.test_news_macro
uv run python -m examples.test_market_data
uv run python -m examples.test_filings
```

## Testing

Grove has two layers of testing:

**Unit tests** cover the deterministic scorer functions with no API keys or external services needed:

```bash
PYTHONPATH=. uv run pytest tests/ -v
```

**Eval harness** provides two Langfuse-backed suites that run the live agents and score output quality:
- Orchestrator suite (`grove-orchestrator-v1`): 21 end-to-end cases across 5 routing types, scored for routing accuracy and citation integrity
- Subagent suite (`grove-subagent-v1`): 6 isolation cases (2 per subagent), scored with an LLM judge per-subagent rubric

See [evals/README.md](evals/README.md) for commands, scorer details, and cost notes.

## Project Structure

```
agents/
  orchestrator.py           # Routes queries, synthesizes final report
  middleware/               # SystemDateMiddleware, TavilyExtractSummarizer, ModelRetryMiddleware
  prompts/                  # Shared prompt snippets (citations guidance)
  tools/                    # Single source of truth for all tools
  subagents/
    news_macro/             # Sentiment, news, macro context
    market_data/            # Quantitative metrics via yfinance
    filings/                # 10-K analysis via EDGAR + PageIndex
  skills/
    analyzing-sentiment/    # Skill: sentiment analysis workflow
    analyzing-financials/   # Skill: financial metrics workflow
    analyzing-filings/      # Skill: SEC filing analysis workflow
    deep-dive-analysis/     # Skill: full deep-dive report workflow
    comparing-stocks/       # Skill: multi-ticker comparison workflow
clients/                    # LLM, Tavily, Langfuse, PageIndex singletons
evals/                      # Eval harness, datasets, and scorers (see evals/README.md)
lib/PageIndex/              # Cloned from github.com/VectifyAI/PageIndex
```

## Adding a Subagent

1. Create `agents/subagents/<name>/` with `__init__.py`, `agent.py`, `system_prompt.py`
2. Add shared tools to `agents/tools/`; subagent-specific tools go in `agent.py`
3. Register in `orchestrator.py` and update the routing section of the orchestrator system prompt
