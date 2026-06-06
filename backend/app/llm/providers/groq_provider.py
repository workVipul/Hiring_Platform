import base64
import json
import logging
import re
from typing import Sequence

import httpx

from app.core.config import settings
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY or settings.GROK_API_KEY
        self.model = settings.LLM_MODEL
        self.vision_model = settings.LLM_VISION_MODEL or settings.LLM_MODEL

    async def complete(self, system: str, user: str, max_tokens: int = 1000) -> str:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured")

        import asyncio
        import logging
        import random
        
        logger = logging.getLogger(__name__)
        
        models_to_try = [self.model]
        if self.model != "llama-3.1-8b-instant":
            models_to_try.append("llama-3.1-8b-instant")
        if "llama3-8b-8192" not in models_to_try:
            models_to_try.append("llama3-8b-8192")

        max_retries = 4
        base_delay = 1.0

        async with httpx.AsyncClient() as client:
            for model_attempt_idx, model in enumerate(models_to_try):
                for attempt in range(max_retries + 1):
                    try:
                        res = await client.post(
                            f"{self.BASE_URL}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": model,
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
                    except httpx.HTTPStatusError as e:
                        is_rate_limit = (e.response.status_code == 429) or (
                            e.response.status_code == 400 and "rate limit" in e.response.text.lower()
                        )
                        
                        if is_rate_limit:
                            if attempt < max_retries:
                                retry_after = e.response.headers.get("retry-after")
                                sleep_time = 0.0
                                if retry_after:
                                    try:
                                        sleep_time = float(retry_after)
                                    except ValueError:
                                        pass
                                if not sleep_time:
                                    reset_val = e.response.headers.get("x-ratelimit-reset")
                                    if reset_val:
                                        try:
                                            sleep_time = float(reset_val.rstrip('s'))
                                        except ValueError:
                                            pass
                                if not sleep_time:
                                    sleep_time = base_delay * (2.0 ** attempt) + random.uniform(0.5, 1.5)
                                else:
                                    sleep_time += random.uniform(0.5, 1.5)
                                
                                logger.warning(
                                    f"Groq API returned rate limit for model {model}. "
                                    f"Retrying in {sleep_time:.2f}s... (Attempt {attempt + 1}/{max_retries})"
                                )
                                await asyncio.sleep(sleep_time)
                                continue
                            else:
                                if model_attempt_idx < len(models_to_try) - 1:
                                    logger.warning(
                                        f"Model {model} rate limited and out of retries. "
                                        f"Falling back to next model: {models_to_try[model_attempt_idx + 1]}"
                                    )
                                    break
                                raise
                        raise


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
            raise ValueError("GROQ_API_KEY is not configured")
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
            "provider": "groq",
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
            "VISION_REQUEST provider=groq model=%s image_count=%s",
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
            raw = res.json()["choices"][0]["message"]["content"]
            return parse_json_response(raw)

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
