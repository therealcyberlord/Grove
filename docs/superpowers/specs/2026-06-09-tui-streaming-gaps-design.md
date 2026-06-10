# TUI Streaming Gaps Design

## Problem

Two UX gaps in the TUI sidebar during a run:

1. **Pause after submit**: Between the user hitting Enter and the first real sidebar item appearing (subagent or tool), the sidebar is blank for 2-4 seconds while the orchestrator LLM decides what to call.

2. **Ticker lookup invisible**: When the orchestrator calls `ticker_lookup` (e.g. resolving "Apple" → AAPL), it happens silently — nothing appears in the sidebar.

## Solution

### Fix 1 — Client-side "Thinking..." spinner (cli/app.py only)

When `run_started` arrives from the server, immediately add a "Thinking..." `ActivityItem` spinner to the sidebar and store a reference in `self._thinking_item`. On the first subsequent `subagent_started` or `tool_started` event, remove it by calling `self._thinking_item.remove()`.

This covers both orchestrator runs and direct subagent runs (`/news_macro TSLA`). For direct subagent runs there is no routing step, but there is still a brief delay before the first tool call, so the spinner is still useful.

**Why client-side and not a server event:** No server changes are needed. The spinner is a placeholder that covers the gap; accuracy isn't required because it's always replaced within the first real server event.

**Timing:**
- User submits → `run_query` is called
- Network round trip (~100ms) → `run_started` arrives → spinner added
- LLM routes query (2-4s) → first `subagent_started` or `tool_started` → spinner removed

### Fix 2 — Orchestrator tool events visible (server/streaming.py only)

In `translate_orchestrator_events`, add handlers for `on_tool_start` / `on_tool_end` where `lc_agent_name == "Grove"` and `name != "task"`. These are orchestrator-level tools like `ticker_lookup`. Emit them as `tool_started` / `tool_completed` events without a `"subagent"` key so the TUI renders them at top level in the sidebar (not nested).

The TUI's `_apply_event` already handles top-level tool events correctly (the `if "subagent" in data` branch falls through to `activity.start_item(label)`) — no TUI changes needed for Fix 2.

**Sidebar sequence for "Give me a deep dive on Apple":**
```
⠋ Thinking...                ← Fix 1: appears on run_started
⠙ ticker_lookup...           ← Fix 2: Thinking dismissed, tool appears
✓ ticker_lookup (0.3s)
⠹ news_macro...
  ⠸ tavily_news_search...
⠼ market_data...
⠴ filings...
✓ news_macro (12.4s)
✓ market_data (8.1s)
✓ filings (18.2s)
```

**Sidebar sequence for "/news_macro TSLA":**
```
⠋ Thinking...                ← Fix 1
⠙ tavily_news_search...      ← Thinking dismissed
✓ tavily_news_search (1.2s)
⠹ tavily_extract...
✓ news_macro (14.3s)
```

## Files Changed

| File | Change |
|---|---|
| `cli/app.py` | Add `_thinking_item: ActivityItem \| None` field; add spinner on `run_started`; dismiss on first `subagent_started` or `tool_started` |
| `server/streaming.py` | Add `on_tool_start`/`on_tool_end` handlers for `lc_agent_name == "Grove"` (non-`task` tools) in `translate_orchestrator_events` |

## Out of Scope

- Humanizing tool names in the sidebar (e.g. `ticker_lookup` → "Looking up ticker") — raw tool names are consistent with existing behavior
- Showing the LLM's streaming tokens from the orchestrator's planning phase
- Any changes to subagent streaming behavior
