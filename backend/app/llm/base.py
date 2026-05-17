from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int = 1000) -> str:
        """Send a prompt and return response text."""

    @abstractmethod
    async def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> dict:
        """Send a prompt expecting JSON and return a parsed dict."""
