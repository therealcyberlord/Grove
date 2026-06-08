# Grove TUI: a Claude Code-style terminal client

## Context

Grove's orchestrator and subagents currently run only as a Python library — invoked via one-off scripts in `examples/` or the eval harness, with no HTTP layer and no way to watch a run happen live. To make Grove usable as an interactive research tool, we want a terminal application (TUI) that feels like Claude Code or OpenCode: you type a query, watch the agent's progress stream in live (which subagents are running, when they finish), and see the final markdown report render as it's generated.

This requires two new additive pieces: a streaming HTTP layer in front of the orchestrator (and, directly, the subagents), and a terminal client that consumes it. Neither touches the existing orchestrator, subagents, or tools.

Like Claude Code's slash commands, the TUI also lets you bypass the orchestrator's routing and call one specialist directly — e.g. `/filings NVDA` runs only the filings subagent instead of letting the orchestrator decide which subagents to dispatch.

## Architecture

```
Textual TUI (runs in your terminal)
   │  POST /runs            {"query": "..."}              (plain query → orchestrator)
   │  POST /runs/{name}     {"query": "..."}              (/name query → that subagent directly)
   │  ← streamed newline-delimited JSON events, both routes
   ▼
FastAPI streaming server (new)
   │  orchestrator.astream_events(...)        market_data["runnable"].astream_events(...)
   │                                          news_macro["runnable"].astream_events(...)
   ▼                                          filings["runnable"].astream_events(...)
Existing orchestrator → subagents → tools (unchanged)
```

Each query is a **one-shot run**: no shared conversation state across queries (matches how the orchestrator and subagents are invoked today — single message in, single report out — and how `examples/` and the eval harness work). Multi-turn conversation is a possible future enhancement, not in scope here.

## Component 1: Streaming server (`server/`)

New package alongside `agents/`, `clients/`, etc.

- **`server/app.py`** — FastAPI app instance. A lifespan hook calls the existing `init_db()` and `ensure_bucket()` (today these only run from `main.py`'s CLI `main()`). Two routes:
  - `POST /runs` — runs the full orchestrator (routes across subagents itself)
  - `POST /runs/{subagent_name}` — runs one subagent directly (`subagent_name` is `news_macro`, `market_data`, or `filings` — the same `"name"` keys their `CompiledSubAgent` dicts already declare; an unknown name returns `404`)
- **`server/schemas.py`** — minimal request schema: `{"query": str}`, used by both routes. (The existing `schemas/agents.py::AgentRunRequest` carries `model`/`summarize_model` fields that aren't actually wired into the orchestrator — `build_openrouter_client()` is called with a hardcoded model in `agents/orchestrator.py`. Rather than stretch that schema to fit, define a small new one for this endpoint.)
- **`server/streaming.py`** — the translation layer: consumes `<runnable>.astream_events(inputs, version="v2")` (the orchestrator for `/runs`, the chosen subagent's `["runnable"]` for `/runs/{name}`) and yields simplified JSON events as newline-delimited text via `StreamingResponse(media_type="application/x-ndjson")`. Each route uses a different event vocabulary (below) because the natural unit of "live progress" differs: for the orchestrator it's *which subagent is running*; for a single subagent run directly, there's no wrapper level left — the natural unit is *which tool it's calling* (EDGAR fetch, PageIndex lookup, Tavily search, yfinance pull, etc.), which is exactly the detail Claude Code surfaces for its own tool calls.

### Event schema — `/runs` (orchestrator)

| Event | Emitted when | Payload |
|---|---|---|
| `run_started` | run begins | `{"query": str}` |
| `subagent_started` | `on_tool_start` where the tool name is `task` (DeepAgents' subagent-dispatch mechanism) and the input identifies the subagent | `{"id": str, "name": str}` (e.g. `"market_data"`) |
| `subagent_completed` | matching `on_tool_end` for that dispatch | `{"id": str, "name": str, "duration_s": float}` |
| `report_chunk` | `on_chat_model_stream` originating from the **orchestrator's own** model — filtered by `metadata.lc_agent_name == "Grove"` so subagent-internal token streams (their own LLM calls, summarizers, judges) are not leaked into the UI | `{"text": str}` |
| `run_completed` | run finishes successfully | `{}` |
| `error` | an exception propagates out of the run | `{"message": str}` |

This produces exactly the granularity decided on for orchestrator runs: subagent-level progress (not individual tool calls inside each subagent — Tavily searches, yfinance lookups, PageIndex reads stay hidden) plus the final synthesized report streaming token-by-token.

The `id` field is the underlying event's `run_id` (a unique string per tool invocation), passed straight through. It's needed because the same subagent can be dispatched more than once in a single run (e.g. a comparison query calls `market_data` once per ticker) — without a correlation id, the TUI couldn't tell two concurrent or sequential invocations of the same subagent apart, or pair each `_started` with the right `_completed`.

**Verified empirically** (via a probe script run against a live query): `on_tool_start`/`on_tool_end` events for the `task` tool carry `data["input"] = {"subagent_type": "market_data", "description": "..."}`, and `metadata["lc_agent_name"]` is `"Grove"` for the orchestrator's own chat-model-stream events vs. `"{name}_subagent"` (e.g. `"news_macro_subagent"`) for nested subagent generations — confirming the filter approach above is reliable, not speculative.

### Event schema — `/runs/{subagent_name}` (direct subagent)

| Event | Emitted when | Payload |
|---|---|---|
| `run_started` | run begins | `{"query": str, "subagent": str}` |
| `tool_started` | `on_tool_start` for any tool the subagent calls (e.g. `fetch_and_index_filing`, `pageindex_get_structure`, `tavily_news_search`, `yfinance_get_market_data` — including deepagents' built-in filesystem tools like `read_file`, since Claude Code surfaces its own internal tool calls the same way) | `{"id": str, "tool": str, "input": dict}` |
| `tool_completed` | matching `on_tool_end` | `{"id": str, "tool": str, "duration_s": float}` |
| `report_chunk` | `on_chat_model_stream` from the subagent's own model (no nested-agent filtering needed here — there's only one agent) | `{"text": str}` |
| `run_completed` | run finishes successfully | `{}` |
| `error` | an exception propagates out of the run | `{"message": str}` |

This mirrors the orchestrator vocabulary's shape (`*_started`/`*_completed`/`report_chunk`/`run_completed`/`error`) but one level down — `tool_*` instead of `subagent_*` — so the TUI's activity-rendering logic can stay uniform (see Component 2).

### Error handling

Any exception during a run — orchestrator or direct subagent — is caught at the top of the streaming generator, emitted as a single `error` event, and the stream is closed — the TUI surfaces it in the activity panel rather than crashing.

## Component 2: TUI client (`cli/`)

New package using **Textual** (Python TUI framework — keeps everything in the existing `uv`/Python toolchain and lets the client share Pydantic schemas/types with the server if useful).

- **`cli/app.py`** — the Textual `App`. Layout (split-panel, per the approved mockup):
  - **Header**: title + connection status to the server
  - **Left sidebar** (`ActivityLog` widget): a running log of activity-step lines, each with a status indicator (spinner → ✓ / ✗) and elapsed time once known. For an orchestrator run this is seeded with "routing query..." then one line per `subagent_started`/`subagent_completed` pair; for a direct subagent run it's one line per `tool_started`/`tool_completed` pair (e.g. "fetch_and_index_filing(NVDA)... done"). Both map onto the same `(label, status, elapsed)` shape, so the widget doesn't need to know which kind of run produced them.
  - **Main pane**: a `Markdown` widget that re-renders incrementally as `report_chunk` text accumulates — so headers, tables, links etc. render properly as the report streams, not as raw text
  - **Bottom input bar**: a prompt (`Input` widget) where the user types a query or a slash command; disabled while a run is in progress and re-enabled on `run_completed`/`error`
- **`cli/commands.py`** — slash-command parsing: input starting with `/` is split into `(subagent_name, rest_of_query)`, e.g. `/filings NVDA` → `("filings", "NVDA")`. A small fixed set of valid names (`news_macro`, `market_data`, `filings` — matching the `CompiledSubAgent["name"]` values) is used for validation and for the in-app command hint/autocomplete; an unrecognized `/name` shows an inline error in the activity log without making a request. Plain text with no leading `/` is sent to `/runs` as today; a recognized `/name ...` is sent to `/runs/{name}`.
- **`cli/client.py`** — thin async client wrapping `httpx.AsyncClient.stream("POST", ...)`, with one method per route (`stream_run(query)` → `/runs`, `stream_subagent_run(name, query)` → `/runs/{name}`), parsing each NDJSON line and yielding typed events to the app via an async generator
- Submitting a new query (slash command or plain) clears the previous run's sidebar and report pane and starts fresh (one-shot model — no accumulated context)
- Launch: `PYTHONPATH=. uv run python -m cli.app`, consistent with how `examples/` and `evals/` are invoked. A `[project.scripts]` entry (e.g. `grove-tui` / `grove-server`) can also be added since `pyproject.toml` currently defines none.

### New dependencies

`fastapi`, `uvicorn`, `textual`, `httpx` — none of which currently exist in `pyproject.toml`.

### Configuration

The TUI needs to know where the server lives. Add a `GROVE_API_URL` setting (default `http://localhost:8000`) — for local dev this is enough; no auth layer for v1 since this is a local developer tool, matching "minimal."

## Testing / Verification

Manual end-to-end check (no existing test infrastructure covers HTTP streaming or TUI rendering, and adding it would be disproportionate to a "minimal" interactive tool):

1. Start the server: `uv run uvicorn server.app:app --reload`
2. Launch the TUI in a separate terminal: `PYTHONPATH=. uv run python -m cli.app`
3. Type a query that triggers multiple subagents (e.g. "Give me an in-depth analysis of NVDA") and confirm:
   - The sidebar shows "routing...", then each subagent transitioning from running → done with timing
   - The main pane fills in with formatted markdown as the report streams (not all at once at the end)
   - The input bar is disabled mid-run and re-enabled when the report completes
4. Try a single-subagent query (e.g. "What's the sentiment for CELH?") and confirm only the relevant subagent appears
5. Type a slash command (e.g. `/filings NVDA`) and confirm:
   - The request goes to `/runs/filings`, not `/runs`
   - The sidebar shows tool-level activity (`fetch_and_index_filing`, `pageindex_get_structure`, `pageindex_get_page_content`, ...) rather than subagent-level activity
   - The report streams and renders the same way as an orchestrator run
6. Type an invalid slash command (e.g. `/nonsense NVDA`) and confirm the TUI shows an inline error without making a request
7. Trigger an error path (e.g. stop the server mid-run, or query an invalid ticker) and confirm the TUI surfaces it gracefully rather than hanging or crashing

## Out of scope (possible future work)

- Multi-turn conversation / session memory
- Mid-run cancellation
- Streaming individual tool calls within each subagent
- Authentication
