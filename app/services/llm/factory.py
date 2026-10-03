"""
LLM Provider Factory.
"""

import logging
from app.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.gemini import GeminiLLMProvider
from app.services.llm.openai import OpenAILLMProvider
from app.services.llm.groq import GroqLLMProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "gemini": GeminiLLMProvider,
    "openai": OpenAILLMProvider,
    "groq": GroqLLMProvider,
}


def get_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """
    Return an LLM provider instance based on provider_name or settings.LLM_PROVIDER.
    """
    name = (provider_name or settings.LLM_PROVIDER).strip().lower()
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        raise ValueError(
            f"Unsupported LLM provider: {name!r}. Supported providers: {list(_PROVIDERS.keys())}"
        )
    return provider_cls()
