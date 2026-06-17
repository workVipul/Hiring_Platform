from functools import lru_cache

from app.core.config import settings
from app.llm.base import LLMProvider


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    return build_llm_provider(settings.LLM_PROVIDER)


@lru_cache(maxsize=1)
def get_vision_llm_provider() -> LLMProvider:
    return build_llm_provider(settings.VISION_LLM_PROVIDER)


def build_llm_provider(provider_name: str) -> LLMProvider:
    provider = provider_name.lower()
    if provider == "groq":
        from app.llm.providers.groq_provider import GroqProvider

        return GroqProvider()

    if provider == "grok":
        from app.llm.providers.grok_provider import GrokProvider

        return GrokProvider()

    if provider == "anthropic":
        from app.llm.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()

    if provider == "gemini":
        from app.services.gemini_provider import GeminiProvider

        return GeminiProvider()

    raise ValueError(f"Unknown LLM provider: {provider}. Valid: groq, grok, anthropic, gemini")
