# TUI Streaming Gaps Design

## Problem

Three UX gaps in the TUI sidebar during a run:

1. **Pause after submit**: Between the user hitting Enter and the first real sidebar item appearing (subagent or tool), the sidebar is blank for 2-4 seconds while the orchestrator LLM decides what to call.

2. **Ticker lookup invisible**: When the orchestrator calls `ticker_lookup` (e.g. resolving "Apple" → AAPL), it happens silently — nothing appears in the sidebar.

3. **Raw tool names are shown**: Non-technical users see internal names like `tavily_news_search`, `yfinance_get_market_data`, `fetch_and_index_filing`. These are meaningless to end users.

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
⠋ Thinking...                    ← Fix 1: appears on run_started
⠙ Looking up ticker...           ← Fix 2: Thinking dismissed, tool appears (Fix 3: friendly label)
✓ Looking up ticker (0.3s)
⠹ News & Sentiment...
  ⠸ Searching news...
⠼ Market Data...
⠴ SEC Filings...
✓ News & Sentiment (12.4s)
✓ Market Data (8.1s)
✓ SEC Filings (18.2s)
```

**Sidebar sequence for "/news_macro TSLA":**
```
⠋ Thinking...                    ← Fix 1
⠙ Searching news...              ← Thinking dismissed (Fix 3: friendly label)
✓ Searching news (1.2s)
⠹ Reading article...
✓ News & Sentiment (14.3s)
```

### Fix 3 — Humanized labels (cli/app.py only)

A static mapping dict translates raw tool/subagent names into user-friendly labels before display. The mapping lives in `cli/app.py` (or extracted to `cli/labels.py` if it grows large). Both in-progress labels (spinner) and completion labels (✓) use the friendly name.

**Tool name mapping:**

| Raw name | Friendly label |
|---|---|
| `ticker_lookup` | Looking up ticker |
| `tavily_news_search` | Searching news |
| `tavily_finance_search` | Searching financial news |
| `tavily_general_search` | Searching web |
| `tavily_extract` | Reading article |
| `yfinance_get_market_data` | Fetching market data |
| `calculate` | Calculating |
| `fetch_and_index_filing` | Fetching SEC filing |
| `pageindex_get_document` | Opening filing |
| `pageindex_get_structure` | Reading filing structure |
| `pageindex_get_page_content` | Reading filing section |

**Subagent name mapping:**

| Raw name | Friendly label |
|---|---|
| `news_macro` | News & Sentiment |
| `market_data` | Market Data |
| `filings` | SEC Filings |

Unknown names fall back to the raw name (no breakage if new tools are added).

**Sidebar sequence after all three fixes ("Give me a deep dive on Apple"):**
```
⠋ Thinking...
⠙ Looking up ticker...
✓ Looking up ticker (0.3s)
⠹ News & Sentiment...
  ⠸ Searching news...
⠼ Market Data...
⠴ SEC Filings...
✓ News & Sentiment (12.4s)
✓ Market Data (8.1s)
✓ SEC Filings (18.2s)
```

## Files Changed

| File | Change |
|---|---|
| `cli/app.py` | Add `_thinking_item: ActivityItem \| None` field; add spinner on `run_started`; dismiss on first `subagent_started` or `tool_started`; add tool/subagent label mapping; apply mapping in `_apply_event` |
| `server/streaming.py` | Add `on_tool_start`/`on_tool_end` handlers for `lc_agent_name == "Grove"` (non-`task` tools) in `translate_orchestrator_events` |

## Out of Scope

- Showing the LLM's streaming tokens from the orchestrator's planning phase
- Any changes to subagent streaming behavior
