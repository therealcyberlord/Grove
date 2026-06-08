"""Request schema shared by the orchestrator and direct-subagent run routes."""
from pydantic import BaseModel


class RunRequest(BaseModel):
    query: str
