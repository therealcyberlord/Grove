from functools import lru_cache

from tavily import AsyncTavilyClient
import os


@lru_cache(maxsize=1)
def get_tavily_client() -> AsyncTavilyClient:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY is not set in environment variables.")
    return AsyncTavilyClient(api_key=api_key)
