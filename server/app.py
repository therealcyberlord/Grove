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
