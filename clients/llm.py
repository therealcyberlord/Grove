"""Shared LLM factory for all Grove agents."""
import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_openrouter import ChatOpenRouter

load_dotenv()


def build_claude_client(model: str = "anthropic:claude-sonnet-4.6", temperature: float = 0.1, max_retries=3):
    """Return a ChatAnthropic instance at the specified temperature."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    return init_chat_model(model=model, temperature=temperature, api_key=api_key, max_retries=max_retries)


def build_openrouter_client(model: str = "deepseek/deepseek-v4-pro", temperature: float = 0.1, max_retries=3):
    """Return a ChatOpenRouter instance at the specified temperature."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    return ChatOpenRouter(model=model, temperature=temperature, api_key=api_key, max_retries=max_retries)
