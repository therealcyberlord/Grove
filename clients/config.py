from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str
    anthropic_api_key: str = ""
    tavily_api_key: str
    edgar_identity: str
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = ""
    database_url: str
    test_database_url: str
    s3_endpoint_url: str
    s3_bucket: str = "grove-filings"
    s3_access_key: str
    s3_secret_key: str


settings = Settings()
