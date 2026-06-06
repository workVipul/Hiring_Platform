from abc import ABC, abstractmethod
from typing import Sequence


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int = 1000) -> str:
        """Send a prompt and return response text."""

    @abstractmethod
    async def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> dict:
        """Send a prompt expecting JSON and return a parsed dict."""

    async def complete_json_with_images(
        self,
        system: str,
        user: str,
        images: Sequence[tuple[str, bytes, str]],
        max_tokens: int = 3500,
    ) -> dict:
        """Send a vision prompt expecting JSON and return a parsed dict."""
        raise NotImplementedError("Configured LLM provider does not support vision JSON requests")
