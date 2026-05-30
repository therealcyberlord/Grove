from functools import lru_cache

from tavily import AsyncTavilyClient

from clients.config import settings


@lru_cache(maxsize=1)
def get_tavily_client() -> AsyncTavilyClient:
    return AsyncTavilyClient(api_key=settings.tavily_api_key)
