# Grove

**The Analyst's Workbench** - A financial research assistant that generates detailed, sourced stock reports on demand. Ask a question (sentiment, deep analysis, comparison) and Grove delegates to specialist subagents, then synthesizes a markdown report with cited sources.

## How It Works

```
user query
  ↓
orchestrator - decides which subagents to call based on query type
  ├─ news_macro(ticker)    → sentiment, key events, macro context, forward scenarios
  ├─ market_data(ticker)   → valuation, margins, cash flows, balance sheet
  └─ filings(ticker)       → 10-K risk factors, management tone, audit, red flags
  ↓
orchestrator synthesizes → final markdown report with investment thesis and all sources
```

**Query routing:**
- `"What is the sentiment for CELH?"` → `news_macro` only
- `"Give me an in-depth analysis of NVDA"` → all three subagents
- `"Compare AAPL vs MSFT"` → each subagent called per ticker in parallel

## Tech Stack

- **LLM**: DeepSeek V4 Pro via OpenRouter; Gemini Flash Lite for article summarization
- **Orchestration**: DeepAgents - orchestrator-subagent pattern
- **Search**: Tavily (news, finance, extract)
- **Market data**: yfinance
- **SEC filings**: edgartools + PageIndex
- **Observability**: Langfuse
- **Package manager**: uv (Python 3.12+)

## Setup

### 1. Clone the repository and install dependencies

```bash
git clone <repo-url>
cd backend
uv sync
```

### 2. Clone PageIndex into lib/

PageIndex is a local library (not a pip package) used for 10-K document navigation.

```bash
git clone https://github.com/VectifyAI/PageIndex lib/PageIndex
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```
OPENROUTER_API_KEY=         # Required - DeepSeek and Gemini via OpenRouter
TAVILY_API_KEY=             # Required - all search tools
LANGFUSE_PUBLIC_KEY=        # Required - observability
LANGFUSE_SECRET_KEY=        # Required - observability
LANGFUSE_BASE_URL=          # Required - e.g. https://us.cloud.langfuse.com
ANTHROPIC_API_KEY=          # Optional - Claude API (not used by default agents)
EDGAR_IDENTITY=             # Optional - SEC EDGAR User-Agent (default: "Grove Agent (dev)")
```

Langfuse is required at startup - the app will raise clearly if any of the three Langfuse variables are missing.

## Running

```bash
# Full in-depth analysis
uv run python -m examples.test_orchestrator

# Individual subagents
uv run python -m examples.test_news_macro
uv run python -m examples.test_market_data
uv run python -m examples.test_filings
```

## Project Structure

```
agents/
  orchestrator.py              # Routes queries to subagents, synthesizes final report
  middleware/                  # Cross-cutting middleware applied per agent
    system_date.py             # Injects today's date into every model call
    tavily_extract_summarizer.py  # Compresses long article extracts using Gemini
  prompts/
    citations.py               # Shared CITATIONS_GUIDANCE prompt snippet
  tools/                       # Single source of truth for all tools
    tavily.py                  # tavily_news_search, tavily_finance_search, tavily_extract
    yahoo_finance.py           # yfinance_get_market_data, ticker_lookup
    pageindex.py               # pageindex_get_structure, pageindex_get_page_content
    calculator.py              # Safe eval calculator
  subagents/
    news_macro/                # Sentiment, news events, macro context
    market_data/               # Quantitative metrics via yfinance
    filings/                   # Qualitative 10-K analysis via EDGAR + PageIndex
clients/
  llm.py                       # LLM client factories
  tavily.py                    # Tavily client singleton
  langfuse.py                  # Langfuse client singleton
  pageindex.py                 # PageIndex client wrapper
lib/
  PageIndex/                   # Cloned from github.com/VectifyAI/PageIndex
schemas/
  agents.py                    # AgentRunRequest Pydantic model
documents/                     # 10-K markdown files fetched from EDGAR (auto-created)
workspace/                     # PageIndex index storage (auto-created)
examples/                      # Manual run scripts
```

## Data Sources

| Subagent | Data Source | Coverage |
|---|---|---|
| `news_macro` | Tavily (news + finance search) | Recent news, analyst ratings, macro signals |
| `market_data` | Yahoo Finance (yfinance) | Valuation, margins, cash flows, balance sheet |
| `filings` | SEC EDGAR + PageIndex | 10-K risk factors, MD&A, audit opinion |

## Adding a New Subagent

1. Create `agents/subagents/<name>/` with `__init__.py`, `agent.py`, `system_prompt.py`
2. Add any shared tools to `agents/tools/`; subagent-specific tools go in `agent.py`
3. Register the subagent in `orchestrator.py` and update the routing section of the orchestrator system prompt
