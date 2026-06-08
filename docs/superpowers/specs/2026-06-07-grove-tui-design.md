# Grove TUI: a Claude Code-style terminal client

## Context

Grove's orchestrator and subagents currently run only as a Python library — invoked via one-off scripts in `examples/` or the eval harness, with no HTTP layer and no way to watch a run happen live. To make Grove usable as an interactive research tool, we want a terminal application (TUI) that feels like Claude Code or OpenCode: you type a query, watch the agent's progress stream in live (which subagents are running, when they finish), and see the final markdown report render as it's generated.

This requires two new additive pieces: a streaming HTTP layer in front of the orchestrator, and a terminal client that consumes it. Neither touches the existing orchestrator, subagents, or tools.

## Architecture

```
Textual TUI (runs in your terminal)
   │  POST /runs {"query": "..."}
   │  ← streamed newline-delimited JSON events
   ▼
FastAPI streaming server (new)
   │  orchestrator.astream_events(version="v2")
   ▼
Existing orchestrator → subagents → tools (unchanged)
```

Each query is a **one-shot run**: no shared conversation state across queries (matches how the orchestrator is invoked today — single message in, single report out — and how `examples/` and the eval harness work). Multi-turn conversation is a possible future enhancement, not in scope here.

## Component 1: Streaming server (`server/`)

New package alongside `agents/`, `clients/`, etc.

- **`server/app.py`** — FastAPI app instance. A lifespan hook calls the existing `init_db()` and `ensure_bucket()` (today these only run from `main.py`'s CLI `main()`). Single route: `POST /runs`.
- **`server/schemas.py`** — minimal request schema: `{"query": str}`. (The existing `schemas/agents.py::AgentRunRequest` carries `model`/`summarize_model` fields that aren't actually wired into the orchestrator — `build_openrouter_client()` is called with a hardcoded model in `agents/orchestrator.py`. Rather than stretch that schema to fit, define a small new one for this endpoint.)
- **`server/streaming.py`** — the translation layer: consumes `orchestrator.astream_events(inputs, version="v2")` and yields simplified JSON events as newline-delimited text via `StreamingResponse(media_type="application/x-ndjson")`.

### Event schema

| Event | Emitted when | Payload |
|---|---|---|
| `run_started` | run begins | `{"query": str}` |
| `subagent_started` | `on_tool_start` where the tool name is `task` (DeepAgents' subagent-dispatch mechanism — confirmed in `deepagents/middleware/async_subagents.py`) and the input identifies the subagent | `{"name": str}` (e.g. `"market_data"`) |
| `subagent_completed` | matching `on_tool_end` for that dispatch | `{"name": str, "duration_s": float}` |
| `report_chunk` | `on_chat_model_stream` originating from the **orchestrator's own** model — filtered by run name/tags so subagent-internal token streams (their own LLM calls, summarizers, judges) are not leaked into the UI | `{"text": str}` |
| `run_completed` | run finishes successfully | `{}` |
| `error` | an exception propagates out of the run | `{"message": str}` |

This produces exactly the granularity decided on: subagent-level progress (not individual tool calls inside each subagent — Tavily searches, yfinance lookups, PageIndex reads stay hidden) plus the final synthesized report streaming token-by-token.

**Filtering orchestrator vs. subagent model streams**: `astream_events` tags/names events with the run hierarchy, so `report_chunk` events are distinguished from a subagent's internal generation by checking the event's parent run corresponds to the orchestrator's own model node, not a `task` tool's nested graph run. This needs to be verified empirically against the actual event shapes DeepAgents/LangGraph produce — the implementation plan should include a quick exploratory script that prints raw `astream_events` output for a sample query before wiring up the filter logic.

### Error handling

Any exception during the run is caught at the top of the streaming generator, emitted as a single `error` event, and the stream is closed — the TUI surfaces it in the activity panel rather than crashing.

## Component 2: TUI client (`cli/`)

New package using **Textual** (Python TUI framework — keeps everything in the existing `uv`/Python toolchain and lets the client share Pydantic schemas/types with the server if useful).

- **`cli/app.py`** — the Textual `App`. Layout (split-panel, per the approved mockup):
  - **Header**: title + connection status to the server
  - **Left sidebar** (`ActivityLog` widget): a running log seeded with "routing query...", then one line per subagent showing a status indicator (spinner → ✓ / ✗) and elapsed time once known, populated from `subagent_started` / `subagent_completed` events
  - **Main pane**: a `Markdown` widget that re-renders incrementally as `report_chunk` text accumulates — so headers, tables, links etc. render properly as the report streams, not as raw text
  - **Bottom input bar**: a prompt (`Input` widget) where the user types a query; disabled while a run is in progress and re-enabled on `run_completed`/`error`
- **`cli/client.py`** — thin async client wrapping `httpx.AsyncClient.stream("POST", ...)`, parsing each NDJSON line and yielding typed events to the app via an async generator
- Submitting a new query clears the previous run's sidebar and report pane and starts fresh (one-shot model — no accumulated context)
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
5. Trigger an error path (e.g. stop the server mid-run, or query an invalid ticker) and confirm the TUI surfaces it gracefully rather than hanging or crashing

## Out of scope (possible future work)

- Multi-turn conversation / session memory
- Mid-run cancellation
- Streaming individual tool calls within each subagent
- Authentication
