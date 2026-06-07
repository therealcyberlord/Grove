from functools import lru_cache

from clients.config import settings


def _langfuse_configured() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key and settings.langfuse_base_url)


@lru_cache(maxsize=1)
def get_langfuse_client():
    if not _langfuse_configured():
        return None
    from langfuse import Langfuse
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_base_url,
    )


def get_langfuse_callback():
    """Return a LangfuseCallbackHandler configured via the global Langfuse client, or None if not configured."""
    if not _langfuse_configured():
        return None
    get_langfuse_client()  # ensures global Langfuse client is initialised with our credentials
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
    return LangfuseCallbackHandler()
