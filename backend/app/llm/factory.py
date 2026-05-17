from functools import lru_cache

from app.core.config import settings
from app.llm.base import LLMProvider


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER.lower()

    if provider == "groq":
        from app.llm.providers.groq_provider import GroqProvider

        return GroqProvider()

    if provider == "grok":
        from app.llm.providers.grok_provider import GrokProvider

        return GrokProvider()

    if provider == "anthropic":
        from app.llm.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Valid: groq, grok, anthropic")
