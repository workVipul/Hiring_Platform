from app.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    async def complete(self, system: str, user: str, max_tokens: int = 1000) -> str:
        raise NotImplementedError("Anthropic provider is reserved for a later task.")

    async def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> dict:
        raise NotImplementedError("Anthropic provider is reserved for a later task.")
