"""Middleware that injects today's date into the system message on every model call."""
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ContextT, ModelRequest, ModelResponse, ResponseT


class SystemDateMiddleware(AgentMiddleware[Any, ContextT, ResponseT]):
    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        system = f"Today's date is {date.today().isoformat()}.\n\n{request.system_message or ''}"
        return handler(request.override(system_message=system))

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        system = f"Today's date is {date.today().isoformat()}.\n\n{request.system_message or ''}"
        return await handler(request.override(system_message=system))
