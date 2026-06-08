"""Unit tests for the orchestrator/subagent astream_events translation layer."""
import asyncio

from langchain_core.messages import AIMessageChunk

from server.streaming import to_ndjson, translate_orchestrator_events, translate_subagent_events


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


def test_to_ndjson_encodes_events_as_utf8_ndjson():
    events = _fake_events(
        {"event": "run_started", "data": {"query": "hello"}},
        {"event": "run_completed", "data": {}},
    )
    lines = asyncio.run(_collect(to_ndjson(events)))
    assert lines == [
        b'{"event": "run_started", "data": {"query": "hello"}}\n',
        b'{"event": "run_completed", "data": {}}\n',
    ]
