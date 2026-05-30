# Grove Backend

"The Analyst's Workbench" - v1. A financial research assistant that generates detailed, sourced stock reports on demand. A user asks a question (sentiment, deep analysis, comparison) and the orchestrator delegates to specialist subagents as needed, then synthesizes a markdown report with cited sources.

## Tech Stack

- **LLM**: DeepSeek V4 Pro via OpenRouter (`build_openrouter_client()`); Gemini Flash Lite for Tavily extract summarization
- **Orchestration**: DeepAgents (`deepagents`) - orchestrator-subagent pattern
- **Tools**: LangChain `@tool` decorators, async-first, blocking libs run in executor
- **Package manager**: `uv` - use `uv run` or `uv add`, not pip
- **Python**: 3.12+

## Project Structure

```
agents/
  orchestrator.py              # Orchestrator - routes queries to subagents, synthesizes report
  middleware/                  # Cross-cutting middleware applied per agent
    system_date.py             # SystemDateMiddleware - injects today's date into every model call
    tavily_extract_summarizer.py  # TavilyExtractSummarizer - compresses long extract results
  prompts/
    citations.py               # CITATIONS_GUIDANCE shared prompt snippet
  tools/                       # Single source of truth for all tools
    tavily.py                  # Tavily search and extract tools
    yahoo_finance.py           # Yahoo Finance market data + ticker_lookup
    pageindex.py               # PageIndex document navigation tools
    calculator.py              # Safe eval calculator tool
  subagents/
    news_macro/                # Sentiment, news events, macro context
    market_data/               # Quantitative metrics via yfinance
    filings/                   # Qualitative 10-K analysis via EDGAR + PageIndex
clients/
  llm.py                       # build_claude_client() and build_openrouter_client() factories
  tavily.py                    # get_tavily_client() singleton
  langfuse.py                  # get_langfuse_client() singleton - required, raises if not configured
  pageindex.py                 # get_pageindex_client() - wraps local lib/PageIndex
evals/
  experiments.py               # Langfuse experiment runner (orchestrator + subagent experiments)
  dataset.py                   # EvalCase + SubagentEvalCase definitions; eval_dataset + subagent_eval_dataset
  scorers/
    routing.py                 # score_routing - Jaccard similarity of detected vs expected subagents
    structure.py               # score_structure - required/forbidden section header checks
    urls.py                    # score_no_fabricated_urls - all report URLs must come from tool results
lib/
  PageIndex/                   # PageIndex local library (not a pip package)
schemas/
  agents.py                    # AgentRunRequest Pydantic model
documents/                     # 10-K markdown files fetched from EDGAR (auto-created)
workspace/                     # PageIndex index storage (auto-created)
examples/                      # Manual run scripts for subagents and orchestrator
main.py                        # Stub entry point
```

Each subagent folder has the same layout:
- `agent.py` - defines the `CompiledSubAgent` dict (name, description, runnable) and any subagent-specific tools
- `system_prompt.py` - `SYSTEM_PROMPT` string constant

## Orchestrator-Subagent Pattern

The orchestrator receives the user query and decides which subagents to call (and for which tickers). Subagents are deepagents themselves - they run their own tool-calling loop and produce a self-contained final response. The orchestrator only ever sees each subagent's **last message**, so that response must be complete.

```
user query
  ↓
orchestrator (deepagents) - decides subagents + tickers based on query
  ├─ [ticker_lookup if name given]
  ├─ call news_macro(ticker)     → self-contained markdown summary + sources
  ├─ call market_data(ticker)    → self-contained markdown summary + sources
  └─ call filings(ticker)        → self-contained markdown summary + sources
  ↓
orchestrator synthesizes → final markdown report with all sources
```

**Query routing examples:**
- "What is the sentiment for CELH?" → `news_macro` only
- "Give me an in-depth analysis of CELH" → all three subagents
- "Compare NVDA vs AMD" → each subagent called per ticker (parallel where possible)

## Subagent Final Response Requirements

Each subagent's final response is the only thing the orchestrator sees. System prompts must instruct subagents to:
1. Include all relevant findings and data points
2. Cite every source used (inline markdown links for Tavily URLs, "Source: Yahoo Finance" for yfinance, "Source: [section name]" for SEC filings)
3. Never fabricate or construct URLs - only cite what tools returned
4. Structure output as markdown sections for easy synthesis

Shared citation guidance lives in `agents/prompts/citations.py` (`CITATIONS_GUIDANCE`) - include it in subagent system prompts.

## LLM Temperatures

All agents use factories from `clients/llm.py`:
- `0.1` - market_data, filings (deterministic, numbers-focused)
- `0.2` - news_macro, orchestrator, TavilyExtractSummarizer

## Middleware

Middleware is registered per-agent in `create_agent(middleware=[...])`. All middleware lives in `agents/middleware/`.

- **`SystemDateMiddleware`** - prepends `"Today's date is {date}."` to the system message on every model call. Used by `news_macro` (date-sensitive news queries) and `market_data` (anchors "real-time" price data to the report run date).
- **`TavilyExtractSummarizer`** - intercepts `tavily_extract` tool results and summarizes articles above a character threshold using Gemini Flash Lite. Prevents context bloat from long articles. Used by `news_macro`.
- **`ModelRetryMiddleware`** - retries on model errors with exponential backoff (`max_retries=3, backoff_factor=2.0`). Used by all subagents.
- **`ToolCallLimitMiddleware`** - caps expensive tool calls per run. Used by `filings` to limit `pageindex_get_page_content` to 5 calls.

## Tools

All tools live in `agents/tools/` - subagents import from there, never define their own duplicate tools. Subagent-specific tools (e.g. `fetch_and_index_filing`) are defined in `agent.py` alongside the subagent.

`@tool` functions must be async (or sync for CPU-only operations). Blocking libraries (edgartools, PageIndex, yfinance) run inside `asyncio.get_running_loop().run_in_executor(None, sync_fn)`.

Tools return a `dict` with an `"error": str | None` key where failure is possible, so the agent can handle failures gracefully without raising.

### Tools by file

**`tavily.py`** - `tavily_news_search`, `tavily_finance_search`, `tavily_general_search`, `tavily_extract`

**`yahoo_finance.py`** - `yfinance_get_market_data` (valuation, margins, cash flows, balance sheet, buybacks), `ticker_lookup` (resolve company name → ticker)

**`pageindex.py`** - `pageindex_get_document`, `pageindex_get_structure`, `pageindex_get_page_content`

**`calculator.py`** - `calculate` (safe `eval()` with only `math` symbols; use for CAGR, ROIC, margin %)

### Tools by subagent

**orchestrator** - `ticker_lookup` (resolve names before dispatching)

**news_macro** - `tavily_news_search`, `tavily_finance_search`, `tavily_extract`

**market_data** - `yfinance_get_market_data`, `calculate`

**filings** - `fetch_and_index_filing` (defined in `filings/agent.py`), `pageindex_get_structure`, `pageindex_get_page_content`

### Filings workflow

The filings subagent uses EDGAR + PageIndex for 10-K analysis. `fetch_and_index_filing(ticker)` must be called first - it fetches the latest 10-K via `edgartools`, converts it to markdown, saves it to `documents/`, and indexes it with PageIndex. Returns a `doc_id` and `period`. Subsequent calls for the same ticker hit a filename-based cache in the PageIndex client.

### Shared clients

All singletons live in `clients/`:
- Tavily: `from clients.tavily import get_tavily_client`
- LLM: `from clients.llm import build_openrouter_client, build_claude_client`
- PageIndex: `from clients.pageindex import get_pageindex_client`
- Langfuse: `from clients.langfuse import get_langfuse_client`

Do not instantiate these directly in tool or agent files.

## Environment Variables

```
OPENROUTER_API_KEY         # Primary LLM (DeepSeek, Gemini via OpenRouter)
ANTHROPIC_API_KEY          # Claude API (build_claude_client - not used by default agents)
TAVILY_API_KEY             # All Tavily search tools
EDGAR_IDENTITY             # SEC EDGAR User-Agent (default: "Grove Agent (dev)")
LANGFUSE_PUBLIC_KEY        # Observability - required; wired per-call via LangfuseCallbackHandler
LANGFUSE_SECRET_KEY        # Observability - required
LANGFUSE_BASE_URL          # Observability - required
```

## Key Conventions

**American English** throughout - `analyze`, `synthesize`, `normalize`, `optimize`.

**System prompts** - no decorative separators (`━━━`), no "OUTPUT FORMAT" sections. Keep prompts to what actually changes model behavior. Always include the self-contained final response requirement and `CITATIONS_GUIDANCE`.

**Missing data** - tools return `None` for unavailable fields, never `0.0` as a placeholder.

**No fabricated URLs** - tools only return URLs from Tavily responses or EDGAR. Agents must never construct or guess URLs.

**Sources** - every factual claim in a subagent response must be traceable to a tool result. yfinance data is cited as "Source: Yahoo Finance". SEC filing content is cited as "Source: [section name]".

**No em dashes** - the orchestrator system prompt explicitly forbids em dashes (-) in output. Keep this consistent in prompts.

## Adding a New Subagent

1. Create `agents/subagents/<name>/` with `__init__.py`, `agent.py`, `system_prompt.py`.
2. Add any new shared tools to `agents/tools/`. Subagent-specific tools go in `agent.py`.
3. Register the subagent in `orchestrator.py` (`subagents=[...]`) and update the routing section of the orchestrator system prompt.

## Known Issues / Watch-outs

- The PageIndex client cache (via `lru_cache`) is process-scoped. Concurrent requests for the same ticker during indexing could race. Acceptable for single-run usage; needs a lock or external cache for server deployment.
- `yfinance` label matching for FCF, ROE, and ROA derivation uses string matching against DataFrame index labels - may break if yfinance changes its schema.
- `tavily_general_search` is defined but not currently wired to any subagent. Available for future use.

## Evaluation

The eval harness is implemented and live. Run via:

```bash
# Full orchestrator eval suite
PYTHONPATH=. uv run python -m evals.experiments

# Filter by routing type
PYTHONPATH=. uv run python -m evals.experiments sentiment market_data

# Subagent isolation evals
PYTHONPATH=. uv run python -m evals.experiments subagent

# Filter by subagent
PYTHONPATH=. uv run python -m evals.experiments subagent news_macro
```

### Datasets

Two Langfuse datasets are auto-synced on each run:

| Dataset | Langfuse name | Cases | Purpose |
|---|---|---|---|
| `eval_dataset` | `grove-orchestrator-v1` | 21 cases | End-to-end orchestrator quality |
| `subagent_eval_dataset` | `grove-subagent-v1` | 6 cases | Per-subagent isolation |

`eval_dataset` covers 5 routing types: `sentiment` (7), `market_data` (4), `filings` (3), `deep_dive` (4), `comparison` (3). Cases are defined in `evals/dataset.py` — edit there, not in the Langfuse UI.

### Scorers (orchestrator)

| Scorer | Type | What it checks |
|---|---|---|
| `subagent_routing` | Rule-based | Jaccard similarity of detected vs expected subagents (partial credit) |
| `no_fabricated_urls` | Rule-based | Every URL in report came from a tool result |

Subagent detection works by fingerprinting tool names: `tavily_*` → news_macro, `yfinance_*`/`calculate` → market_data, `pageindex_*`/`fetch_and_index_filing` → filings. Section header checks were intentionally omitted — the orchestrator adapts section titles to query type (e.g. earnings queries get custom headers), so header assertions produce false failures.

### Scorers (subagent)

| Scorer | Type | What it checks |
|---|---|---|
| `subagent_quality` | Rule-based | Output >200 chars AND contains a citation ("source" or "http") |
| `no_fabricated_urls` | Rule-based | Same URL check as orchestrator |

### LLM-as-judge (Langfuse-native)

Two LLM-as-judge evaluators are configured directly in Langfuse and fire automatically on every trace with name "Grove":

- **Agent Helpfulness** — does the report address what the user asked?
- **Source Citation** — are all factual claims backed by cited sources?

These run on both live production traces and experiment traces created by the eval runner.

## Next Steps

### Phase 2 Roadmap

- **Watchlist alerts** - background monitor: cron-triggered runs against stored user tickers; email digest
- **Comparison improvements** - side-by-side structured table output for multi-ticker comparisons
- **User profiles** - persist preferred tickers, sectors, report depth preferences
- **Sell signals** - thesis-invalidation check on held positions: outputs hold / trim / exit with rationale
