from functools import lru_cache

from dotenv import load_dotenv
from langfuse import get_client

load_dotenv()


@lru_cache(maxsize=1)
def get_langfuse_client():
    """Return the Langfuse client. Reads credentials from env vars.

    Raises ValueError if LANGFUSE_PUBLIC_KEY / SECRET_KEY are not set or tracing is disabled.
    """
    client = get_client()
    if not client._tracing_enabled:
        raise ValueError(
            "Langfuse client is disabled. Set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, "
            "and LANGFUSE_BASE_URL environment variables."
        )
    return client
