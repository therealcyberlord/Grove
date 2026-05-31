import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str
    anthropic_api_key: str = ""
    tavily_api_key: str
    edgar_identity: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_base_url: str


settings = Settings()

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_base_url)
