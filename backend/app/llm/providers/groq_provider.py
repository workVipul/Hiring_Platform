import json
import re

import httpx

from app.core.config import settings
from app.llm.base import LLMProvider


class GroqProvider(LLMProvider):
    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY or settings.GROK_API_KEY
        self.model = settings.LLM_MODEL

    async def complete(self, system: str, user: str, max_tokens: int = 1000) -> str:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured")

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
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
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
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    async def transcribe_audio(self, filename: str, data: bytes, content_type: str | None = None) -> str:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured")

        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.BASE_URL}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={
                    "model": "whisper-large-v3-turbo",
                    "response_format": "json",
                    "language": "en",
                    "temperature": "0",
                },
                files={"file": (filename, data, content_type or "application/octet-stream")},
                timeout=120,
            )
            res.raise_for_status()
            return res.json()["text"]
