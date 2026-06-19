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
        async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0, read=120.0)) as client:
            async with client.stream("POST", f"{self._base_url}{path}", json={"query": query}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield json.loads(line)
