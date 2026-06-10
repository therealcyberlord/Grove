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
            event_type = ev["event"]
            name = ev["name"]
            run_id = ev["run_id"]
            data = ev.get("data") or {}
            metadata = ev.get("metadata") or {}
            lc_agent_name = metadata.get("lc_agent_name", "")
            if event_type == "on_tool_start" and name == "task":
                subagent_name = data["input"]["subagent_type"]
                started_at[run_id] = time.monotonic()
                yield {"event": "subagent_started", "data": {"id": run_id, "name": subagent_name}}
            elif event_type == "on_tool_end" and name == "task":
                subagent_name = data["input"]["subagent_type"]
                duration_s = time.monotonic() - started_at.pop(run_id, time.monotonic())
                yield {"event": "subagent_completed", "data": {"id": run_id, "name": subagent_name, "duration_s": round(duration_s, 1)}}
            elif event_type == "on_tool_start" and name != "task" and lc_agent_name.endswith("_subagent"):
                subagent = lc_agent_name.removesuffix("_subagent")
                started_at[run_id] = time.monotonic()
                yield {"event": "tool_started", "data": {"id": run_id, "tool": name, "subagent": subagent, "input": data["input"]}}
            elif event_type == "on_tool_end" and name != "task" and lc_agent_name.endswith("_subagent"):
                subagent = lc_agent_name.removesuffix("_subagent")
                duration_s = time.monotonic() - started_at.pop(run_id, time.monotonic())
                yield {"event": "tool_completed", "data": {"id": run_id, "tool": name, "subagent": subagent, "duration_s": round(duration_s, 1)}}
            elif event_type == "on_tool_start" and name != "task" and lc_agent_name == "Grove":
                started_at[run_id] = time.monotonic()
                yield {"event": "tool_started", "data": {"id": run_id, "tool": name, "input": data["input"]}}
            elif event_type == "on_tool_end" and name != "task" and lc_agent_name == "Grove":
                duration_s = time.monotonic() - started_at.pop(run_id, time.monotonic())
                yield {"event": "tool_completed", "data": {"id": run_id, "tool": name, "duration_s": round(duration_s, 1)}}
            elif event_type == "on_chat_model_stream" and lc_agent_name == "Grove":
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
            event_type = ev["event"]
            name = ev["name"]
            run_id = ev["run_id"]
            data = ev.get("data") or {}

            if event_type == "on_tool_start":
                started_at[run_id] = time.monotonic()
                yield {"event": "tool_started", "data": {"id": run_id, "tool": name, "input": data["input"]}}
            elif event_type == "on_tool_end":
                duration_s = time.monotonic() - started_at.pop(run_id, time.monotonic())
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
