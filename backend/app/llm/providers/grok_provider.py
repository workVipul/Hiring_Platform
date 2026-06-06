import base64
import json
import logging
import re
from typing import Sequence

import httpx

from app.core.config import settings
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class GrokProvider(LLMProvider):
    BASE_URL = "https://api.x.ai/v1"

    def __init__(self):
        self.api_key = settings.GROK_API_KEY
        self.model = settings.LLM_MODEL
        self.vision_model = settings.LLM_VISION_MODEL or settings.LLM_MODEL

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
        return parse_json_response(raw)

    async def complete_json_with_images(
        self,
        system: str,
        user: str,
        images: Sequence[tuple[str, bytes, str]],
        max_tokens: int = 3500,
    ) -> dict:
        if not self.api_key:
            raise ValueError("GROK_API_KEY is not configured")
        if not images:
            raise ValueError("At least one image is required for vision template generation")

        content: list[dict] = [{"type": "text", "text": user}]
        image_debug = []
        for filename, data, content_type in images:
            encoded = base64.b64encode(data).decode("ascii")
            mime_type = content_type or "image/png"
            image_debug.append({"filename": filename, "bytes": len(data), "mime_type": mime_type})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{encoded}",
                        "detail": "high",
                    },
                }
            )

        message_content_types = [item.get("type") for item in content]
        payload_debug = {
            "provider": "grok",
            "model": self.vision_model,
            "image_count": len(images),
            "message_count": 2,
            "messages": [
                {"role": "system", "content_type": "text", "text_length": len(system)},
                {
                    "role": "user",
                    "content_type": "list",
                    "content_types": message_content_types,
                    "text_length": len(user),
                    "images": image_debug,
                },
            ],
            "response_format": "json_object",
        }
        logger.warning(
            "VISION_REQUEST provider=grok model=%s image_count=%s",
            self.vision_model,
            len(images),
        )
        logger.warning("MESSAGE_CONTENT_TYPES=%s", message_content_types)
        logger.warning("VISION_REQUEST_PAYLOAD_STRUCTURE=%s", payload_debug)

        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.vision_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": content},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
                timeout=180,
            )
            res.raise_for_status()
            return parse_json_response(res.json()["choices"][0]["message"]["content"])


def parse_json_response(raw: str) -> dict:
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
