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
| Storage | PostgreSQL (filing metadata + index), S3/MinIO (filing markdown content) |
| Observability | Langfuse (optional) |
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

**3. Start PostgreSQL and create databases**

```bash
# Create app database and test database
createdb grovedb
createdb grovedb_test
psql -d grovedb -c "GRANT ALL ON SCHEMA public TO <your_user>;"
psql -d grovedb_test -c "GRANT ALL ON SCHEMA public TO <your_user>;"
```

**4. Start S3-compatible object storage** (MinIO for local dev)

```bash
brew install minio/stable/minio
MINIO_ROOT_USER=<minio_user> MINIO_ROOT_PASSWORD=<minio_password> \
  minio server ~/minio-data --address ":9000" --console-address ":9001" &
```

Whatever you choose here must match `S3_ACCESS_KEY` / `S3_SECRET_KEY` in your `.env` (step 5).

MinIO console: `http://localhost:9001`

**5. Configure environment variables.** Create a `.env` in the project root:

```
OPENROUTER_API_KEY=         # Required: DeepSeek and Gemini via OpenRouter
TAVILY_API_KEY=             # Required: all search tools
EDGAR_IDENTITY=             # Required: SEC EDGAR User-Agent
DATABASE_URL=               # Required: e.g. postgresql://<user>:<password>@localhost:5432/grovedb
TEST_DATABASE_URL=          # Required for tests: e.g. postgresql://<user>:<password>@localhost:5432/grovedb_test
S3_ENDPOINT_URL=            # Local MinIO: http://localhost:9000 (omit for AWS S3)
S3_BUCKET=                  # e.g. grove-filings
S3_ACCESS_KEY=              # Must match MINIO_ROOT_USER
S3_SECRET_KEY=              # Must match MINIO_ROOT_PASSWORD
ANTHROPIC_API_KEY=          # Optional: Claude API (not used by default agents)
LANGFUSE_PUBLIC_KEY=        # Optional: observability
LANGFUSE_SECRET_KEY=        # Optional: observability
LANGFUSE_BASE_URL=          # Optional: e.g. https://us.cloud.langfuse.com
```

**6. Seed the database** (one-time, migrates any existing `documents/` and `workspace/` data)

```bash
PYTHONPATH=. uv run python scripts/seed_db.py
```

## Running

MinIO isn't a persistent service - start it before running anything that touches filings or storage (data persists in `~/minio-data` between restarts). Use the same `<minio_user>` / `<minio_password>` you set up in step 4:

```bash
MINIO_ROOT_USER=<minio_user> MINIO_ROOT_PASSWORD=<minio_password> \
  minio server ~/minio-data --address ":9000" --console-address ":9001" &
```

```bash
# Full orchestrator (routes automatically based on query)
PYTHONPATH=. uv run python examples/test_orchestrator.py

# Individual subagents
PYTHONPATH=. uv run python examples/test_news_macro.py
PYTHONPATH=. uv run python examples/test_market_data.py
PYTHONPATH=. uv run python examples/test_filings.py
```

## Testing

Grove has two layers of testing:

**Unit + integration tests** run against a dedicated PostgreSQL test database (`TEST_DATABASE_URL`). Each test is wrapped in a transaction that rolls back on teardown — no data persists between tests.

```bash
PYTHONPATH=. uv run pytest tests/ -v
```

See [tests/README.md](tests/README.md) for fixture details and database setup.

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
