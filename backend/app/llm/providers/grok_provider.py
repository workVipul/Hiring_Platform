import json

import httpx

from app.core.config import settings
from app.llm.base import LLMProvider


class GrokProvider(LLMProvider):
    BASE_URL = "https://api.x.ai/v1"

    def __init__(self):
        self.api_key = settings.GROK_API_KEY
        self.model = settings.LLM_MODEL

    async def complete(self, system: str, user: str, max_tokens: int = 1000) -> str:
        if not self.api_key:
            raise ValueError("GROK_API_KEY is not configured")

        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]

    async def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> dict:
        raw = await self.complete(system, user, max_tokens)
        clean = raw.strip()
        if clean.startswith("```json"):
            clean = clean.removeprefix("```json").strip()
        if clean.startswith("```"):
            clean = clean.removeprefix("```").strip()
        if clean.endswith("```"):
            clean = clean.removesuffix("```").strip()
        return json.loads(clean)
