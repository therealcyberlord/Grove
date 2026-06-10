# TUI Streaming Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three UX gaps in the TUI sidebar: an instant "Thinking..." spinner to cover the delay after submit, visibility for orchestrator-level tool calls (e.g. `ticker_lookup`), and human-readable labels for all tool and subagent names.

**Architecture:** Fix 1 is purely client-side — `cli/app.py` adds a spinner on `run_started` and removes it on the first real activity event. Fix 2 is purely server-side — `server/streaming.py` adds handlers that emit `tool_started`/`tool_completed` for non-`task` tools called by the Grove orchestrator (identified by `lc_agent_name == "Grove"`). Fix 3 is a static label mapping in `cli/labels.py` applied throughout `cli/app.py`. No changes to agents, subagents, or shared clients.

**Tech Stack:** Textual 8.2.7 (TUI), FastAPI + NDJSON streaming (server), pytest (tests)

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `server/streaming.py` | Modify | Add orchestrator tool event handlers |
| `tests/server/test_streaming.py` | Modify | Update existing test + add orchestrator tool test |
| `cli/labels.py` | Create | Human-readable label mapping for tools and subagents |
| `tests/cli/test_labels.py` | Create | Unit tests for label mapping functions |
| `cli/app.py` | Modify | Import labels, add spinner field + logic, apply labels |

---

## Task 1: Server — emit orchestrator tool events

**Files:**
- Modify: `server/streaming.py:31-38`
- Modify: `tests/server/test_streaming.py:137-144`

### Context

`translate_orchestrator_events` in `server/streaming.py` currently filters out tool events where `lc_agent_name == "Grove"` (the orchestrator itself). The existing test at line 137 explicitly asserts this filtering. We are flipping this: orchestrator tools (like `ticker_lookup`) should emit `tool_started` / `tool_completed` events without a `"subagent"` key, so the TUI renders them at top level.

The test must be updated FIRST so it fails before the implementation change, then passes after.

---

- [ ] **Step 1: Update the existing test to assert new behavior (it will fail)**

Open `tests/server/test_streaming.py`. Replace lines 137–144:

```python
def test_translate_orchestrator_events_ignores_tool_events_without_subagent_suffix():
    run_id = "tool-run-2"
    events = [
        _nested_tool_event("on_tool_start", "some_tool", run_id, "Grove"),
        _nested_tool_event("on_tool_end", "some_tool", run_id, "Grove", input={}, output=""),
    ]
    result = asyncio.run(_collect(translate_orchestrator_events("q", _fake_events(*events))))
    assert not any(e["event"] in ("tool_started", "tool_completed") for e in result)
```

with:

```python
def test_translate_orchestrator_events_emits_tool_events_for_orchestrator_tools():
    run_id = "tool-run-2"
    events = [
        _nested_tool_event("on_tool_start", "ticker_lookup", run_id, "Grove", input={"query": "Apple Inc"}),
        _nested_tool_event("on_tool_end", "ticker_lookup", run_id, "Grove", input={"query": "Apple Inc"}, output="AAPL"),
    ]
    result = asyncio.run(_collect(translate_orchestrator_events("q", _fake_events(*events))))
    tool_started = next(e for e in result if e["event"] == "tool_started")
    tool_completed = next(e for e in result if e["event"] == "tool_completed")
    assert tool_started["data"]["tool"] == "ticker_lookup"
    assert tool_started["data"]["id"] == run_id
    assert "subagent" not in tool_started["data"]
    assert tool_completed["data"]["tool"] == "ticker_lookup"
    assert tool_completed["data"]["id"] == run_id
    assert tool_completed["data"]["duration_s"] >= 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/xingyubian/Documents/Projects/GenAI/Grove/backend
PYTHONPATH=. uv run pytest tests/server/test_streaming.py::test_translate_orchestrator_events_emits_tool_events_for_orchestrator_tools -v
```

Expected: FAIL — `StopIteration` (no `tool_started` event found).

- [ ] **Step 3: Add orchestrator tool handlers to `server/streaming.py`**

In `server/streaming.py`, the current `translate_orchestrator_events` function has these two elif blocks (lines 31–38):

```python
elif event_type == "on_tool_start" and name != "task" and lc_agent_name.endswith("_subagent"):
    subagent = lc_agent_name.removesuffix("_subagent")
    started_at[run_id] = time.monotonic()
    yield {"event": "tool_started", "data": {"id": run_id, "tool": name, "subagent": subagent, "input": data["input"]}}
elif event_type == "on_tool_end" and name != "task" and lc_agent_name.endswith("_subagent"):
    subagent = lc_agent_name.removesuffix("_subagent")
    duration_s = time.monotonic() - started_at.pop(run_id, time.monotonic())
    yield {"event": "tool_completed", "data": {"id": run_id, "tool": name, "subagent": subagent, "duration_s": round(duration_s, 1)}}
```

Add two more elif blocks immediately after them:

```python
elif event_type == "on_tool_start" and name != "task" and lc_agent_name == "Grove":
    started_at[run_id] = time.monotonic()
    yield {"event": "tool_started", "data": {"id": run_id, "tool": name, "input": data["input"]}}
elif event_type == "on_tool_end" and name != "task" and lc_agent_name == "Grove":
    duration_s = time.monotonic() - started_at.pop(run_id, time.monotonic())
    yield {"event": "tool_completed", "data": {"id": run_id, "tool": name, "duration_s": round(duration_s, 1)}}
```

The complete updated function body (for reference) should have the event processing block in this order:
1. `on_tool_start` + `name == "task"` → `subagent_started`
2. `on_tool_end` + `name == "task"` → `subagent_completed`
3. `on_tool_start` + `name != "task"` + `lc_agent_name.endswith("_subagent")` → `tool_started` (with subagent)
4. `on_tool_end` + `name != "task"` + `lc_agent_name.endswith("_subagent")` → `tool_completed` (with subagent)
5. *(new)* `on_tool_start` + `name != "task"` + `lc_agent_name == "Grove"` → `tool_started` (no subagent)
6. *(new)* `on_tool_end` + `name != "task"` + `lc_agent_name == "Grove"` → `tool_completed` (no subagent)
7. `on_chat_model_stream` + `lc_agent_name == "Grove"` → `report_chunk`

- [ ] **Step 4: Run full streaming test suite**

```bash
PYTHONPATH=. uv run pytest tests/server/test_streaming.py -v
```

Expected: ALL PASS. 6 tests total.

- [ ] **Step 5: Commit**

```bash
git add server/streaming.py tests/server/test_streaming.py
git commit -m "feat: emit tool_started/completed for orchestrator-level tools"
```

---

## Task 2: Label mapping module

**Files:**
- Create: `cli/labels.py`
- Create: `tests/cli/test_labels.py`

---

- [ ] **Step 1: Write failing tests**

Create `tests/cli/test_labels.py`:

```python
"""Unit tests for TUI display label mapping."""
from cli.labels import subagent_label, tool_label


def test_tool_label_returns_friendly_name_for_known_tools():
    assert tool_label("ticker_lookup") == "Looking up ticker"
    assert tool_label("tavily_news_search") == "Searching news"
    assert tool_label("tavily_finance_search") == "Searching financial news"
    assert tool_label("tavily_general_search") == "Searching web"
    assert tool_label("tavily_extract") == "Reading article"
    assert tool_label("yfinance_get_market_data") == "Fetching market data"
    assert tool_label("calculate") == "Calculating"
    assert tool_label("fetch_and_index_filing") == "Fetching SEC filing"
    assert tool_label("pageindex_get_document") == "Opening filing"
    assert tool_label("pageindex_get_structure") == "Reading filing structure"
    assert tool_label("pageindex_get_page_content") == "Reading filing section"


def test_tool_label_falls_back_to_raw_name_for_unknown_tools():
    assert tool_label("some_new_tool") == "some_new_tool"


def test_subagent_label_returns_friendly_name_for_known_subagents():
    assert subagent_label("news_macro") == "News & Sentiment"
    assert subagent_label("market_data") == "Market Data"
    assert subagent_label("filings") == "SEC Filings"


def test_subagent_label_falls_back_to_raw_name_for_unknown_subagents():
    assert subagent_label("unknown_agent") == "unknown_agent"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. uv run pytest tests/cli/test_labels.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'cli.labels'`

- [ ] **Step 3: Create `cli/labels.py`**

```python
_TOOL_LABELS: dict[str, str] = {
    "ticker_lookup": "Looking up ticker",
    "tavily_news_search": "Searching news",
    "tavily_finance_search": "Searching financial news",
    "tavily_general_search": "Searching web",
    "tavily_extract": "Reading article",
    "yfinance_get_market_data": "Fetching market data",
    "calculate": "Calculating",
    "fetch_and_index_filing": "Fetching SEC filing",
    "pageindex_get_document": "Opening filing",
    "pageindex_get_structure": "Reading filing structure",
    "pageindex_get_page_content": "Reading filing section",
}

_SUBAGENT_LABELS: dict[str, str] = {
    "news_macro": "News & Sentiment",
    "market_data": "Market Data",
    "filings": "SEC Filings",
}


def tool_label(name: str) -> str:
    return _TOOL_LABELS.get(name, name)


def subagent_label(name: str) -> str:
    return _SUBAGENT_LABELS.get(name, name)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. uv run pytest tests/cli/test_labels.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/labels.py tests/cli/test_labels.py
git commit -m "feat: add human-readable label mapping for tool and subagent names"
```

---

## Task 3: TUI — spinner and label application

**Files:**
- Modify: `cli/app.py`

### Context

`cli/app.py` is 168 lines. The changes are:

1. Add `from cli.labels import subagent_label, tool_label` to imports.
2. Add `_thinking_item: ActivityItem | None` to class-level annotations.
3. In `on_mount`, add `self._thinking_item = None`.
4. In `run_query`, add `self._thinking_item = None` at the top (stale refs from prior run).
5. Add a `_dismiss_thinking` method.
6. In `_apply_event`, update every event handler branch.

There are no unit tests for Textual widget behavior (consistent with the existing test suite). Verify manually by running the TUI.

---

- [ ] **Step 1: Add import and class annotation**

In `cli/app.py`, add `tool_label, subagent_label` to the import from `cli`:

```python
from cli.labels import subagent_label, tool_label
from cli.widgets import ActivityItem, ActivityLog, CommandInput, CommandSuggestions
```

Add `_thinking_item` to the class-level annotation block (after `_subagent_last_child`):

```python
class GroveApp(App):
    CSS_PATH = "styles.tcss"

    _items_by_id: dict[str, ActivityItem]
    _auto_scroll: bool
    _programmatic_scroll: bool
    _subagent_last_child: dict[str, ActivityItem]
    _thinking_item: ActivityItem | None
```

- [ ] **Step 2: Initialize `_thinking_item` in `on_mount` and `run_query`**

In `on_mount`, add `self._thinking_item = None` after `self._subagent_last_child = {}`:

```python
async def on_mount(self) -> None:
    self._items_by_id = {}
    self._subagent_last_child = {}
    self._auto_scroll = True
    self._programmatic_scroll = False
    self._thinking_item = None
    await self._show_welcome()
```

In `run_query`, add `self._thinking_item = None` after `self._subagent_last_child = {}`:

```python
@work(exclusive=True)
async def run_query(self, text: str) -> None:
    self._items_by_id = {}
    self._subagent_last_child = {}
    self._thinking_item = None
    self._auto_scroll = True
    report_scroll = self.query_one("#report-scroll", VerticalScroll)
    self._programmatic_scroll = True
    report_scroll.scroll_home(animate=False)
    self._programmatic_scroll = False

    subagent_name, query = parse_input(text)
    client = GroveClient()
    if subagent_name in SUBAGENT_NAMES:
        stream = client.stream_subagent_run(subagent_name, query)
    else:
        stream = client.stream_run(query)

    async for event in stream:
        await self._apply_event(event)
```

- [ ] **Step 3: Add `_dismiss_thinking` method**

Add this method to `GroveApp` between `_show_welcome` and `on_mouse_scroll_up`:

```python
def _dismiss_thinking(self) -> None:
    if self._thinking_item is not None:
        self._thinking_item.remove()
        self._thinking_item = None
```

- [ ] **Step 4: Update `_apply_event` — all branches**

Replace the entire `_apply_event` method with:

```python
async def _apply_event(self, event: dict) -> None:
    activity = self.query_one("#sidebar", ActivityLog)
    event_type = event["event"]

    if event_type == "run_started":
        activity.clear_items()
        report = self.query_one("#report", Markdown)
        await report.update("")
        self._thinking_item = activity.start_item("Thinking...")

    elif event_type == "subagent_started":
        self._dismiss_thinking()
        data = event["data"]
        label = subagent_label(data["name"])
        item = activity.start_item(f"{label}...")
        self._items_by_id[data["id"]] = item
        self._subagent_last_child[data["name"]] = item

    elif event_type == "tool_started":
        self._dismiss_thinking()
        data = event["data"]
        label = tool_label(data["tool"])
        display = f"{label}..."
        if "subagent" in data:
            last = self._subagent_last_child.get(data["subagent"])
            if last:
                item = activity.insert_nested_after(display, after=last)
            else:
                item = activity.start_nested_item(display)
            self._subagent_last_child[data["subagent"]] = item
        else:
            item = activity.start_item(display)
        self._items_by_id[data["id"]] = item

    elif event_type in ("subagent_completed", "tool_completed"):
        data = event["data"]
        item = self._items_by_id.pop(data["id"], None)
        if item:
            if "name" in data:
                friendly = subagent_label(data["name"])
            else:
                friendly = tool_label(data.get("tool", ""))
            item.mark_done(f"✓ {friendly} ({data['duration_s']}s)")

    elif event_type == "report_chunk":
        report = self.query_one("#report", Markdown)
        await report.append(event["data"]["text"])
        if self._auto_scroll:
            report_scroll = self.query_one("#report-scroll", VerticalScroll)
            self._programmatic_scroll = True
            report_scroll.scroll_end(animate=False)
            self._programmatic_scroll = False

    elif event_type == "error":
        self._dismiss_thinking()
        for item in self._items_by_id.values():
            item.mark_done("✗ interrupted")
        self._items_by_id = {}

    elif event_type == "run_completed":
        pass
```

- [ ] **Step 5: Verify existing CLI tests still pass**

```bash
PYTHONPATH=. uv run pytest tests/cli/ -v
```

Expected: ALL PASS (command parsing tests + new label tests).

- [ ] **Step 6: Manual smoke test**

Start the TUI:

```bash
PYTHONPATH=. uv run grove-tui
```

Run an orchestrator query with a company name (to trigger ticker_lookup):

```
Give me a deep dive on Apple
```

Expected sidebar sequence:
```
⠋ Thinking...
⠙ Looking up ticker...
✓ Looking up ticker (0.Xs)
⠹ News & Sentiment...
  ⠸ Searching news...
⠼ Market Data...
⠴ SEC Filings...
✓ News & Sentiment (Xs)
✓ Market Data (Xs)
✓ SEC Filings (Xs)
```

Also run a direct subagent command:

```
/news_macro TSLA
```

Expected: "Thinking..." appears immediately, then disappears when first tool starts, all tool labels are human-readable.

- [ ] **Step 7: Commit**

```bash
git add cli/app.py
git commit -m "feat: add Thinking spinner, humanized labels, and orchestrator tool visibility in TUI"
```
