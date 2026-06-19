# Grove TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code-style terminal client (`cli/`) backed by a new FastAPI streaming server (`server/`) that fronts the existing orchestrator and subagents, so a user can type a query (or a `/subagent_name` slash command) and watch live progress + the synthesized markdown report stream into a real terminal.

**Architecture:** `server/streaming.py` translates `<runnable>.astream_events(..., version="v2")` into a small NDJSON event vocabulary (two flavors: orchestrator-level `subagent_started/completed` + `report_chunk`, and subagent-level `tool_started/completed` + `report_chunk`). `server/app.py` exposes `POST /runs` (orchestrator) and `POST /runs/{subagent_name}` (direct subagent) as `StreamingResponse`s over that translation layer. `cli/` is a Textual app with a split-panel layout (activity sidebar + streaming `Markdown` report pane + input bar) that consumes the NDJSON stream via `httpx.AsyncClient.stream` and renders progress/report live; `cli/commands.py` parses `/name query` into direct-subagent dispatch.

**Tech Stack:** FastAPI + `uvicorn` (streaming HTTP server), `httpx` (async streaming HTTP client), Textual (TUI framework), existing `langchain`/`langgraph`/`deepagents` runnables (unchanged) via `astream_events(version="v2")`.

Reference spec: `docs/superpowers/specs/2026-06-07-grove-tui-design.md`

---

## File Structure

New files this plan creates:

```
server/
  __init__.py
  schemas.py        # RunRequest({"query": str})
  streaming.py      # translate_orchestrator_events, translate_subagent_events, to_ndjson
  app.py            # FastAPI app: lifespan (init_db/ensure_bucket), POST /runs, POST /runs/{name}
cli/
  __init__.py
  commands.py       # parse_input: "/name rest" -> (name, rest); plain text -> (None, text)
  client.py         # GroveClient: stream_run / stream_subagent_run over httpx streaming
  widgets.py        # ActivityItem, ActivityLog
  app.py            # GroveApp (Textual): split-panel layout, input handling, event dispatch
  styles.tcss       # Textual stylesheet for the split-panel layout
tests/
  server/
    __init__.py
    test_streaming.py
  cli/
    __init__.py
    test_commands.py
```

Modified:
- `pyproject.toml` — add `fastapi`, `uvicorn[standard]`, `httpx`, `textual` to `dependencies`; add `[project.scripts]` entries `grove-server` / `grove-tui`

---

## Task 1: Add new dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the four new dependencies via `uv add`**

```bash
uv add fastapi "uvicorn[standard]" httpx textual
```

Expected: `uv` resolves and installs the packages, updating `pyproject.toml`'s `dependencies` array and `uv.lock`.

- [ ] **Step 2: Verify the imports resolve**

```bash
uv run python -c "import fastapi, uvicorn, httpx, textual; print('ok')"
```

Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add fastapi, uvicorn, httpx, textual dependencies"
```

---

## Task 2: Create the `server` package and request schema

**Files:**
- Create: `server/__init__.py`
- Create: `server/schemas.py`

- [ ] **Step 1: Create the empty package marker**

Create `server/__init__.py` with empty contents (matches `agents/__init__.py`, `clients/__init__.py`, `schemas/__init__.py` — all empty).

- [ ] **Step 2: Write the request schema**

Create `server/schemas.py`:

```python
"""Request schema shared by the orchestrator and direct-subagent run routes."""
from pydantic import BaseModel


class RunRequest(BaseModel):
    query: str
```

- [ ] **Step 3: Verify it imports**

```bash
uv run python -c "from server.schemas import RunRequest; print(RunRequest(query='hello'))"
```

Expected: `query='hello'`

- [ ] **Step 4: Commit**

```bash
git add server/__init__.py server/schemas.py
git commit -m "feat: add server package with RunRequest schema"
```

---

## Task 3: Build `server/streaming.py` with TDD

This is the translation layer: pure async generators that consume `astream_events` `StreamEvent` dicts and yield the simplified event vocabulary from the spec. No FastAPI or network code here — fully unit-testable with fake async generators.

**Files:**
- Create: `tests/server/__init__.py`
- Create: `tests/server/test_streaming.py`
- Create: `server/streaming.py`

- [ ] **Step 1: Create the test package marker**

Create `tests/server/__init__.py` with empty contents.

- [ ] **Step 2: Write the failing tests**

Create `tests/server/test_streaming.py`:

```python
"""Unit tests for the orchestrator/subagent astream_events translation layer."""
import asyncio

from langchain_core.messages import AIMessageChunk

from server.streaming import translate_orchestrator_events, translate_subagent_events


async def _fake_events(*events):
    for event in events:
        yield event


async def _collect(async_gen):
    return [item async for item in async_gen]


def _tool_event(event_type, name, run_id, *, subagent_type=None, tool_input=None):
    if subagent_type is not None:
        input_data = {"subagent_type": subagent_type, "description": "..."}
    else:
        input_data = tool_input or {}
    return {"event": event_type, "name": name, "run_id": run_id, "metadata": {}, "data": {"input": input_data}}


def _chunk_event(run_id, text, lc_agent_name):
    return {
        "event": "on_chat_model_stream",
        "name": "ChatOpenRouter",
        "run_id": run_id,
        "metadata": {"lc_agent_name": lc_agent_name},
        "data": {"chunk": AIMessageChunk(content=text)},
    }


def test_translate_orchestrator_events_tracks_subagent_dispatch_and_report():
    events = _fake_events(
        _tool_event("on_tool_start", "task", "r1", subagent_type="market_data"),
        _chunk_event("m1", "ignored - subagent's own generation", "market_data_subagent"),
        _tool_event("on_tool_end", "task", "r1", subagent_type="market_data"),
        _chunk_event("m2", "# Report\n", "Grove"),
    )

    results = asyncio.run(_collect(translate_orchestrator_events("analyze NVDA", events)))

    assert results[0] == {"event": "run_started", "data": {"query": "analyze NVDA"}}
    assert results[1] == {"event": "subagent_started", "data": {"id": "r1", "name": "market_data"}}
    assert results[2]["event"] == "subagent_completed"
    assert results[2]["data"]["id"] == "r1"
    assert results[2]["data"]["name"] == "market_data"
    assert isinstance(results[2]["data"]["duration_s"], float)
    assert results[3] == {"event": "report_chunk", "data": {"text": "# Report\n"}}
    assert results[4] == {"event": "run_completed", "data": {}}
    assert len(results) == 5  # the market_data_subagent's own generation is filtered out


def test_translate_orchestrator_events_emits_error_event_on_exception():
    async def _raising():
        yield _tool_event("on_tool_start", "task", "r1", subagent_type="filings")
        raise RuntimeError("orchestrator blew up")

    results = asyncio.run(_collect(translate_orchestrator_events("analyze NVDA", _raising())))

    assert results[-1] == {"event": "error", "data": {"message": "orchestrator blew up"}}


def test_translate_subagent_events_tracks_tool_calls_and_report():
    events = _fake_events(
        _tool_event("on_tool_start", "fetch_and_index_filing", "t1", tool_input={"ticker": "NVDA"}),
        _tool_event("on_tool_end", "fetch_and_index_filing", "t1", tool_input={"ticker": "NVDA"}),
        _chunk_event("m1", "NVDA filed its 10-K...", "filings_subagent"),
    )

    results = asyncio.run(_collect(translate_subagent_events("NVDA", "filings", events)))

    assert results[0] == {"event": "run_started", "data": {"query": "NVDA", "subagent": "filings"}}
    assert results[1] == {"event": "tool_started", "data": {"id": "t1", "tool": "fetch_and_index_filing", "input": {"ticker": "NVDA"}}}
    assert results[2]["event"] == "tool_completed"
    assert results[2]["data"]["id"] == "t1"
    assert results[2]["data"]["tool"] == "fetch_and_index_filing"
    assert isinstance(results[2]["data"]["duration_s"], float)
    assert results[3] == {"event": "report_chunk", "data": {"text": "NVDA filed its 10-K..."}}
    assert results[4] == {"event": "run_completed", "data": {}}


def test_translate_subagent_events_emits_error_event_on_exception():
    async def _raising():
        yield _tool_event("on_tool_start", "tavily_news_search", "t1", tool_input={"query": "NVDA"})
        raise RuntimeError("subagent blew up")

    results = asyncio.run(_collect(translate_subagent_events("NVDA", "news_macro", _raising())))

    assert results[-1] == {"event": "error", "data": {"message": "subagent blew up"}}
```

- [ ] **Step 3: Run the tests and confirm they fail**

```bash
uv run pytest tests/server/test_streaming.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'server.streaming'`

- [ ] **Step 4: Write the implementation**

Create `server/streaming.py`:

```python
"""Translates orchestrator/subagent astream_events streams into a small set of
simplified progress events for the TUI, serialized as newline-delimited JSON."""
import json
import time
from collections.abc import AsyncIterator
from typing import Any

StreamEvent = dict[str, Any]


async def translate_orchestrator_events(query: str, events: AsyncIterator[StreamEvent]) -> AsyncIterator[StreamEvent]:
    """Translate the orchestrator's astream_events into subagent-level progress + report tokens."""
    yield {"event": "run_started", "data": {"query": query}}
    started_at: dict[str, float] = {}
    try:
        async for ev in events:
            event_type = ev.get("event")
            name = ev.get("name")
            run_id = ev.get("run_id")
            data = ev.get("data") or {}

            if event_type == "on_tool_start" and name == "task":
                subagent_name = data["input"]["subagent_type"]
                started_at[run_id] = time.monotonic()
                yield {"event": "subagent_started", "data": {"id": run_id, "name": subagent_name}}
            elif event_type == "on_tool_end" and name == "task":
                subagent_name = data["input"]["subagent_type"]
                duration_s = time.monotonic() - started_at.pop(run_id)
                yield {"event": "subagent_completed", "data": {"id": run_id, "name": subagent_name, "duration_s": round(duration_s, 1)}}
            elif event_type == "on_chat_model_stream" and (ev.get("metadata") or {}).get("lc_agent_name") == "Grove":
                text = data["chunk"].text
                if text:
                    yield {"event": "report_chunk", "data": {"text": text}}
        yield {"event": "run_completed", "data": {}}
    except Exception as exc:
        yield {"event": "error", "data": {"message": str(exc)}}


async def translate_subagent_events(query: str, subagent_name: str, events: AsyncIterator[StreamEvent]) -> AsyncIterator[StreamEvent]:
    """Translate a single subagent's astream_events into tool-level progress + report tokens."""
    yield {"event": "run_started", "data": {"query": query, "subagent": subagent_name}}
    started_at: dict[str, float] = {}
    try:
        async for ev in events:
            event_type = ev.get("event")
            name = ev.get("name")
            run_id = ev.get("run_id")
            data = ev.get("data") or {}

            if event_type == "on_tool_start":
                started_at[run_id] = time.monotonic()
                yield {"event": "tool_started", "data": {"id": run_id, "tool": name, "input": data.get("input", {})}}
            elif event_type == "on_tool_end":
                duration_s = time.monotonic() - started_at.pop(run_id)
                yield {"event": "tool_completed", "data": {"id": run_id, "tool": name, "duration_s": round(duration_s, 1)}}
            elif event_type == "on_chat_model_stream":
                text = data["chunk"].text
                if text:
                    yield {"event": "report_chunk", "data": {"text": text}}
        yield {"event": "run_completed", "data": {}}
    except Exception as exc:
        yield {"event": "error", "data": {"message": str(exc)}}


async def to_ndjson(events: AsyncIterator[StreamEvent]) -> AsyncIterator[bytes]:
    """Serialize a stream of event dicts as newline-delimited JSON bytes for StreamingResponse."""
    async for event in events:
        yield (json.dumps(event) + "\n").encode("utf-8")
```

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
uv run pytest tests/server/test_streaming.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tests/server/__init__.py tests/server/test_streaming.py server/streaming.py
git commit -m "feat: add astream_events translation layer for orchestrator and subagent runs"
```

---

## Task 4: Build `server/app.py` (FastAPI routes + lifespan)

**Files:**
- Create: `server/app.py`

- [ ] **Step 1: Write the FastAPI app**

Create `server/app.py`:

```python
"""FastAPI streaming server fronting the Grove orchestrator and subagents."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from agents.orchestrator import orchestrator
from agents.subagents.filings.agent import filings
from agents.subagents.market_data.agent import market_data
from agents.subagents.news_macro.agent import news_macro
from clients.database import init_db
from clients.storage import ensure_bucket
from server.schemas import RunRequest
from server.streaming import to_ndjson, translate_orchestrator_events, translate_subagent_events

_SUBAGENTS = {subagent["name"]: subagent for subagent in (news_macro, market_data, filings)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_bucket()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/runs")
async def run_orchestrator(request: RunRequest) -> StreamingResponse:
    events = orchestrator.astream_events(
        {"messages": [{"role": "user", "content": request.query}]}, version="v2"
    )
    translated = translate_orchestrator_events(request.query, events)
    return StreamingResponse(to_ndjson(translated), media_type="application/x-ndjson")


@app.post("/runs/{subagent_name}")
async def run_subagent(subagent_name: str, request: RunRequest) -> StreamingResponse:
    subagent = _SUBAGENTS.get(subagent_name)
    if subagent is None:
        raise HTTPException(status_code=404, detail=f"Unknown subagent: {subagent_name}")
    events = subagent["runnable"].astream_events(
        {"messages": [{"role": "user", "content": request.query}]}, version="v2"
    )
    translated = translate_subagent_events(request.query, subagent_name, events)
    return StreamingResponse(to_ndjson(translated), media_type="application/x-ndjson")
```

- [ ] **Step 2: Smoke-test the server starts and routes respond**

In one terminal:

```bash
uv run uvicorn server.app:app
```

Expected: logs show `Application startup complete` (the lifespan hook ran `init_db()`/`ensure_bucket()` without error) and `Uvicorn running on http://127.0.0.1:8000`

In a second terminal, check the 404 path (cheap, no LLM calls):

```bash
curl -s -X POST http://localhost:8000/runs/nonsense -H 'content-type: application/json' -d '{"query": "test"}'
```

Expected: `{"detail":"Unknown subagent: nonsense"}` with a `404` status

Stop the server (`Ctrl+C`) once confirmed.

- [ ] **Step 3: Commit**

```bash
git add server/app.py
git commit -m "feat: add FastAPI streaming routes for orchestrator and direct subagent runs"
```

---

## Task 5: Build `cli/commands.py` (slash-command parsing) with TDD

**Files:**
- Create: `cli/__init__.py`
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/test_commands.py`
- Create: `cli/commands.py`

- [ ] **Step 1: Create the package markers**

Create `cli/__init__.py` and `tests/cli/__init__.py`, both empty.

- [ ] **Step 2: Write the failing tests**

Create `tests/cli/test_commands.py`:

```python
"""Unit tests for slash-command parsing."""
from cli.commands import parse_input


def test_parse_input_returns_plain_query_for_text_without_slash():
    assert parse_input("What is the sentiment for CELH?") == (None, "What is the sentiment for CELH?")


def test_parse_input_splits_slash_command_into_name_and_query():
    assert parse_input("/filings NVDA") == ("filings", "NVDA")


def test_parse_input_handles_slash_command_with_multi_word_query():
    assert parse_input("/market_data compare NVDA and AMD") == ("market_data", "compare NVDA and AMD")


def test_parse_input_handles_slash_command_with_no_query():
    assert parse_input("/filings") == ("filings", "")


def test_parse_input_preserves_unknown_command_name_for_caller_to_validate():
    assert parse_input("/nonsense NVDA") == ("nonsense", "NVDA")
```

- [ ] **Step 3: Run the tests and confirm they fail**

```bash
uv run pytest tests/cli/test_commands.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cli.commands'`

- [ ] **Step 4: Write the implementation**

Create `cli/commands.py`:

```python
"""Slash-command parsing for the Grove TUI - mirrors Claude Code's /command syntax."""

SUBAGENT_NAMES = ("news_macro", "market_data", "filings")


def parse_input(text: str) -> tuple[str | None, str]:
    """Split user input into (subagent_name, query).

    Plain text -> (None, text), routed through the orchestrator.
    "/name rest" -> (name, rest), routed directly to that subagent.

    The returned name is not validated against SUBAGENT_NAMES here - the
    caller checks membership and surfaces unknown commands to the user.
    """
    if not text.startswith("/"):
        return None, text
    name, _, rest = text[1:].partition(" ")
    return name, rest.strip()
```

- [ ] **Step 5: Run the tests and confirm they pass**

```bash
uv run pytest tests/cli/test_commands.py -v
```

Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add cli/__init__.py tests/cli/__init__.py tests/cli/test_commands.py cli/commands.py
git commit -m "feat: add slash-command parsing for direct subagent dispatch"
```

---

## Task 6: Build `cli/client.py` (HTTP streaming client)

**Files:**
- Create: `cli/client.py`

- [ ] **Step 1: Write the client**

Create `cli/client.py`:

```python
"""Async HTTP client that streams NDJSON run events from the Grove server."""
import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

DEFAULT_API_URL = "http://localhost:8000"


class GroveClient:
    """Streams parsed run-event dicts from the Grove FastAPI server."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url or os.environ.get("GROVE_API_URL", DEFAULT_API_URL)

    async def stream_run(self, query: str) -> AsyncIterator[dict[str, Any]]:
        async for event in self._stream("/runs", query):
            yield event

    async def stream_subagent_run(self, subagent_name: str, query: str) -> AsyncIterator[dict[str, Any]]:
        async for event in self._stream(f"/runs/{subagent_name}", query):
            yield event

    async def _stream(self, path: str, query: str) -> AsyncIterator[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self._base_url}{path}", json={"query": query}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield json.loads(line)
```

Notes:
- `timeout=None` is required: agent runs take far longer than `httpx`'s default timeouts, and the connection must stay open for the whole streamed response.
- `GROVE_API_URL` is read via plain `os.environ.get`, not the shared `Settings` (`clients/config.py`) — that class requires many backend secrets (`OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `DATABASE_URL`, ...) that a TUI client talking to a remote server shouldn't need just to start up.

- [ ] **Step 2: Verify it imports and constructs**

```bash
uv run python -c "from cli.client import GroveClient; c = GroveClient(); print(c._base_url)"
```

Expected: `http://localhost:8000`

- [ ] **Step 3: Commit**

```bash
git add cli/client.py
git commit -m "feat: add async HTTP client for streaming Grove server runs"
```

---

## Task 7: Build `cli/widgets.py` (activity sidebar widgets)

**Files:**
- Create: `cli/widgets.py`

- [ ] **Step 1: Write the widgets**

Create `cli/widgets.py`:

```python
"""Activity sidebar widgets for the Grove TUI - track subagent/tool progress lines."""
from textual.containers import VerticalScroll
from textual.widgets import Static

_ICONS = {"running": "◐", "done": "✓", "error": "✗"}


class ActivityItem(Static):
    """A single activity line: a label with a status icon and elapsed time once known."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self._label = label
        self._status = "running"
        self._elapsed: float | None = None
        self._refresh_content()

    def mark_done(self, elapsed: float) -> None:
        self._status = "done"
        self._elapsed = elapsed
        self._refresh_content()

    def mark_interrupted(self) -> None:
        if self._status == "running":
            self._status = "error"
            self._refresh_content()

    def _refresh_content(self) -> None:
        icon = _ICONS[self._status]
        suffix = f" ({self._elapsed:.1f}s)" if self._elapsed is not None else "..."
        self.update(f"{icon} {self._label}{suffix}")


class ActivityLog(VerticalScroll):
    """Scrolling list of activity lines for the current run."""

    def reset(self) -> None:
        self.remove_children()

    def add_note(self, text: str) -> None:
        self.mount(Static(text))

    def start_item(self, label: str) -> ActivityItem:
        item = ActivityItem(label)
        self.mount(item)
        item.scroll_visible()
        return item
```

- [ ] **Step 2: Verify it imports**

```bash
uv run python -c "from cli.widgets import ActivityItem, ActivityLog; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add cli/widgets.py
git commit -m "feat: add activity sidebar widgets for the Grove TUI"
```

---

## Task 8: Build `cli/app.py` and `cli/styles.tcss`

**Files:**
- Create: `cli/app.py`
- Create: `cli/styles.tcss`

- [ ] **Step 1: Write the stylesheet**

Create `cli/styles.tcss`:

```css
Screen {
    layout: vertical;
}

#body {
    height: 1fr;
}

#activity {
    width: 36;
    border-right: solid $primary-background;
    padding: 1;
}

#main {
    width: 1fr;
    padding: 1;
}

#report {
    height: 1fr;
}

#prompt {
    dock: bottom;
}
```

- [ ] **Step 2: Write the Textual app**

Create `cli/app.py`:

```python
"""Grove TUI - a Claude Code-style terminal client for the Grove research backend."""
import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Markdown

from cli.client import GroveClient
from cli.commands import SUBAGENT_NAMES, parse_input
from cli.widgets import ActivityItem, ActivityLog


class GroveApp(App):
    """Split-panel terminal client: activity sidebar + streaming report pane + input bar."""

    CSS_PATH = "styles.tcss"
    TITLE = "Grove"

    def __init__(self) -> None:
        super().__init__()
        self._client = GroveClient()
        self._items_by_id: dict[str, ActivityItem] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield ActivityLog(id="activity")
            with Vertical(id="main"):
                yield Markdown(id="report")
        yield Input(placeholder="Ask a question, or /filings NVDA, /market_data NVDA, /news_macro NVDA", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#prompt", Input).focus()

    def on_input_submitted(self, message: Input.Submitted) -> None:
        text = message.value.strip()
        if not text:
            return
        prompt = self.query_one("#prompt", Input)
        prompt.value = ""
        self.run_query(text)

    @work(exclusive=True)
    async def run_query(self, text: str) -> None:
        prompt = self.query_one("#prompt", Input)
        activity = self.query_one(ActivityLog)
        report = self.query_one("#report", Markdown)

        prompt.disabled = True
        activity.reset()
        await report.update("")
        self._items_by_id = {}

        subagent_name, query = parse_input(text)
        try:
            if subagent_name is None:
                activity.add_note("routing query...")
                stream = self._client.stream_run(query)
            elif subagent_name in SUBAGENT_NAMES:
                stream = self._client.stream_subagent_run(subagent_name, query)
            else:
                activity.add_note(f"✗ Unknown command: /{subagent_name}")
                return

            async for event in stream:
                await self._apply_event(event, activity, report)
        except httpx.HTTPError as exc:
            activity.add_note(f"✗ Connection error: {exc}")
        finally:
            prompt.disabled = False
            prompt.focus()

    async def _apply_event(self, event: dict, activity: ActivityLog, report: Markdown) -> None:
        kind = event.get("event")
        data = event.get("data", {})

        if kind in ("subagent_started", "tool_started"):
            label = data.get("name") or data.get("tool")
            self._items_by_id[data["id"]] = activity.start_item(label)
        elif kind in ("subagent_completed", "tool_completed"):
            item = self._items_by_id.get(data["id"])
            if item is not None:
                item.mark_done(data["duration_s"])
        elif kind == "report_chunk":
            await report.append(data["text"])
        elif kind == "error":
            activity.add_note(f"✗ {data['message']}")
            for item in self._items_by_id.values():
                item.mark_interrupted()


def main() -> None:
    GroveApp().run()


if __name__ == "__main__":
    main()
```

Notes on choices that may look surprising:
- `run_query` is wrapped in `try/except httpx.HTTPError`: Textual's `@work` decorator defaults to `exit_on_error=True`, which would crash the whole app on an unhandled exception (e.g. the server isn't running, or `response.raise_for_status()` raises on a `404`). Catching `httpx.HTTPError` — the base class for httpx's connection and status errors — at this boundary turns a connection failure into an inline activity-log message instead of an app crash. In-run failures (the orchestrator/subagent itself raising) come through the normal stream as an `{"event": "error", ...}` dict and are handled by `_apply_event`, not this `except`.
- `@work(exclusive=True)` cancels any in-flight run when a new query is submitted, matching the one-shot model (submitting a new query starts fresh).

- [ ] **Step 3: Verify the app launches**

```bash
PYTHONPATH=. uv run python -m cli.app
```

Expected: the Textual app opens in the terminal showing the header, an empty activity sidebar, an empty report pane, and a focused input bar reading "Ask a question, or /filings NVDA, ...". Press `Ctrl+C` (or `q` if bound) to quit — confirm the app exits cleanly without a traceback. (The server doesn't need to be running for this step; you're only confirming the UI renders and the input is focused. Don't submit a query yet — that's covered in Task 10.)

- [ ] **Step 4: Commit**

```bash
git add cli/app.py cli/styles.tcss
git commit -m "feat: add Grove TUI Textual app with split-panel layout"
```

---

## Task 9: Add `[project.scripts]` launch entries

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add a `[project.scripts]` table**

`pyproject.toml` currently has no `[project.scripts]` table. Add one after the `dependencies` array (i.e. as a new top-level table, before `[dependency-groups]`):

```toml
[project.scripts]
grove-server = "server.app:app"
grove-tui = "cli.app:main"
```

Wait — `grove-server` pointing at a FastAPI `app` instance is not a valid console-script target (console scripts must reference a *callable*, and running a FastAPI app needs an ASGI server). Drop that entry; the server is launched via `uvicorn` directly per the spec (`uv run uvicorn server.app:app --reload`). Only add the TUI entry point:

```toml
[project.scripts]
grove-tui = "cli.app:main"
```

- [ ] **Step 2: Reinstall so the script entry is registered**

```bash
uv sync
```

Expected: completes without error; `uv run grove-tui --help` is not meaningful for a Textual app, so instead confirm the entry resolves:

```bash
uv run python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='console_scripts') if ep.name == 'grove-tui'])"
```

Expected: `['grove-tui']`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add grove-tui console script entry point"
```

---

## Task 10: Manual end-to-end verification

No existing test infrastructure covers HTTP streaming or TUI rendering, and adding it would be disproportionate to a "minimal" interactive tool — this is the verification approach the spec calls for. This task costs real LLM API tokens (each query below runs the orchestrator and/or subagents against live models and tools) — run it once, attentively, rather than repeatedly.

**Files:** none (manual verification only)

- [ ] **Step 1: Start the server**

In one terminal:

```bash
uv run uvicorn server.app:app --reload
```

Expected: `Uvicorn running on http://127.0.0.1:8000`, no startup errors.

- [ ] **Step 2: Launch the TUI in a second terminal**

```bash
PYTHONPATH=. uv run python -m cli.app
```

Expected: split-panel layout renders, input bar is focused.

- [ ] **Step 3: Run a multi-subagent query through the orchestrator**

Type: `Give me an in-depth analysis of NVDA` and press Enter.

Confirm:
- The activity sidebar shows "routing query..." then a line per dispatched subagent, each transitioning from `◐ name...` (running) to `✓ name (N.Ns)` (done)
- The main pane fills in with rendered markdown (headers, lists, etc. — not raw `#`/`-` characters) as the report streams in, not all at once at the end
- The input bar is disabled while the run is active and re-enabled (and refocused) once the report finishes

- [ ] **Step 4: Run a single-subagent query through the orchestrator**

Type: `What's the sentiment for CELH?` and press Enter.

Confirm only the relevant subagent (`news_macro`) appears in the activity sidebar — the orchestrator routed to one subagent, not all three.

- [ ] **Step 5: Run a direct-subagent slash command**

Type: `/filings NVDA` and press Enter.

Confirm:
- The activity sidebar shows **tool-level** activity (e.g. `fetch_and_index_filing`, `pageindex_get_structure`, `pageindex_get_page_content`), not subagent-level activity — this is the `/runs/filings` route, not `/runs`
- The report streams and renders the same way as an orchestrator run

- [ ] **Step 6: Try an invalid slash command**

Type: `/nonsense NVDA` and press Enter.

Confirm the activity sidebar immediately shows `✗ Unknown command: /nonsense` and **no HTTP request is made** (check the `uvicorn` terminal — no new request log line appears for this submission).

- [ ] **Step 7: Trigger a server-down error path**

Stop the `uvicorn` server (`Ctrl+C` in its terminal), then in the TUI type any query (e.g. `What's the sentiment for AAPL?`) and press Enter.

Confirm the TUI shows an inline `✗ Connection error: ...` message in the activity sidebar, the input bar re-enables, and the app does **not** crash or hang. Restart the server (`uv run uvicorn server.app:app --reload`) afterward if you want to keep testing.

- [ ] **Step 8: Quit cleanly**

Quit the TUI (`Ctrl+C` or the bound quit key) and confirm it exits without a traceback. Stop the server.

No commit for this task — it's verification only. If any step fails, fix the underlying code in the relevant earlier task's files and re-run from Step 1.

---

## Self-Review Notes

**Spec coverage:**
- Streaming server, both routes, lifespan hook, event schemas (orchestrator + subagent), error handling → Tasks 2-4
- `RunRequest` schema replacing `AgentRunRequest` for this purpose → Task 2
- Slash-command parsing + validation set → Task 5
- HTTP streaming client, `GROVE_API_URL` config → Task 6
- Split-panel layout (sidebar + report pane + input bar), activity item shape (label/status/elapsed), markdown rendering, input disable/enable → Tasks 7-8
- New dependencies (`fastapi`, `uvicorn`, `textual`, `httpx`) → Task 1
- Launch commands (`uv run uvicorn server.app:app --reload`, `PYTHONPATH=. uv run python -m cli.app`) and optional `[project.scripts]` entry → Tasks 9-10
- All 7 manual verification scenarios from the spec's Testing/Verification section → Task 10 (steps 3-7, plus launch in steps 1-2 and clean quit in step 8)
- Out-of-scope items (multi-turn, cancellation, per-tool streaming for orchestrator runs, auth) are correctly absent from every task

**Placeholder scan:** No "TBD"/"TODO"/"add appropriate handling" — every step has complete, runnable code or an exact command with an expected result.

**Type consistency:**
- `parse_input` returns `tuple[str | None, str]` in Task 5 and is consumed identically (`subagent_name, query = parse_input(text)`) in Task 8
- `SUBAGENT_NAMES` defined in Task 5, imported and checked (`subagent_name in SUBAGENT_NAMES`) in Task 8
- `GroveClient.stream_run`/`stream_subagent_run` defined in Task 6 with matching call sites in Task 8
- `ActivityLog.reset`/`add_note`/`start_item` and `ActivityItem.mark_done`/`mark_interrupted` defined in Task 7, all four used with matching names and argument shapes in Task 8's `_apply_event`
- Event dict shapes (`{"event": ..., "data": {...}}`, `id`/`name`/`tool`/`duration_s`/`text`/`message` keys) match exactly between `server/streaming.py` (Task 3), the test fixtures (Task 3), and `cli/app.py`'s `_apply_event` (Task 8)
- Caught a real bug during review: my first draft of Task 9 proposed `grove-server = "server.app:app"` as a console script — that's invalid (not a callable, and running an ASGI app needs `uvicorn`). Fixed by dropping it; the server launches via `uvicorn server.app:app` directly, as the spec already specifies.
