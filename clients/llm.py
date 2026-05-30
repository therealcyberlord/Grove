"""Shared LLM factory for all Grove agents."""
from langchain.chat_models import init_chat_model
from langchain_openrouter import ChatOpenRouter

from clients.config import settings


def build_claude_client(model: str = "anthropic:claude-sonnet-4.6", temperature: float = 0.1, max_retries=3):
    return init_chat_model(model=model, temperature=temperature, api_key=settings.anthropic_api_key, max_retries=max_retries)


def build_openrouter_client(model: str = "deepseek/deepseek-v4-pro", temperature: float = 0.1, max_retries=3):
    return ChatOpenRouter(model=model, temperature=temperature, api_key=settings.openrouter_api_key, max_retries=max_retries)
