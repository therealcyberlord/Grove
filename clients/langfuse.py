from functools import lru_cache

from langfuse import Langfuse

from clients.config import settings


@lru_cache(maxsize=1)
def get_langfuse_client():
    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_base_url,
    )
    if not client._tracing_enabled:
        raise ValueError("Langfuse tracing is disabled. Check LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_BASE_URL.")
    return client
