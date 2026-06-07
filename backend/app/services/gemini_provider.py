import asyncio
import asyncio
import json
import logging
import mimetypes
from pathlib import Path
from typing import Sequence

from app.core.config import settings
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

GEMINI_TEMPERATURE = 0.2
GEMINI_RESPONSE_MIME_TYPE = "application/json"
GEMINI_TRUNCATION_RETRY_MULTIPLIER = 2


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.LLM_MODEL
        self.vision_model = settings.LLM_VISION_MODEL or settings.LLM_MODEL

    async def complete(self, system: str, user: str, max_tokens: int = 1000) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        result = await self._generate_content(
            system=system,
            prompt=user,
            images=[],
            max_tokens=max_tokens,
        )
        return json.dumps(result)

    async def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> dict:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        return await self._generate_content(
            system=system,
            prompt=user,
            images=[],
            max_tokens=max_tokens,
        )

    async def complete_json_with_images(
        self,
        system: str,
        user: str,
        images: Sequence[tuple[str, bytes, str]],
        max_tokens: int = 3500,
    ) -> dict:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        if not images:
            raise ValueError("At least one image is required for vision template generation")

        image_debug = [
            {
                "filename": filename,
                "bytes": len(data),
                "mime_type": content_type or "image/png",
            }
            for filename, data, content_type in images
        ]
        logger.warning(
            "VISION_REQUEST provider=gemini model=%s image_count=%s",
            self.vision_model,
            len(images),
        )
        logger.warning("GEMINI_MODEL=%s", self.vision_model)
        logger.warning("IMAGE_COUNT=%s", len(images))
        logger.warning(
            "VISION_REQUEST_PAYLOAD_STRUCTURE=%s",
            {
                "provider": "gemini",
                "model": self.vision_model,
                "image_count": len(images),
                "contents": ["text", *["image" for _ in images]],
                "text_length": len(system) + len(user),
                "images": image_debug,
                "response_mime_type": "application/json",
            },
        )

        try:
            result = await self._generate_content(
                system=system,
                prompt=user,
                images=images,
                max_tokens=max_tokens,
            )
            confidence = _blueprint_confidence(result)
            logger.warning("BLUEPRINT_CONFIDENCE=%s", confidence)
            return result
        except Exception:
            logger.exception("Gemini vision blueprint generation failed; returning fallback blueprint")
            fallback = fallback_blueprint()
            logger.warning("BLUEPRINT_CONFIDENCE=%s", _blueprint_confidence(fallback))
            return fallback

    def generate_blueprint(self, images: list[Path], prompt: str) -> dict:
        return asyncio.run(self.generate_blueprint_async(images, prompt))

    async def generate_blueprint_async(self, images: list[Path], prompt: str) -> dict:
        image_payloads = []
        for image in images:
            mime_type = mimetypes.guess_type(image.name)[0] or "image/png"
            image_payloads.append((image.name, image.read_bytes(), mime_type))
        return await self.complete_json_with_images(
            system="Return only valid JSON for the template blueprint DSL.",
            user=prompt,
            images=image_payloads,
            max_tokens=3500,
        )

    async def _generate_content(
        self,
        *,
        system: str,
        prompt: str,
        images: Sequence[tuple[str, bytes, str]],
        max_tokens: int,
    ) -> dict:
        from google import genai
        from google.genai import types

        parts = [
            types.Part.from_text(
                text=f"{prompt}\n\nReturn ONLY valid JSON. Do not include markdown fences or explanatory text."
            )
        ]
        for _filename, data, content_type in images:
            parts.append(types.Part.from_bytes(data=data, mime_type=content_type or "image/png"))

        model_name = self.vision_model if images else self.model
        async with genai.Client(api_key=self.api_key).aio as client:
            token_budget = max_tokens
            for attempt in range(2):
                logger.warning(
                    "GEMINI_GENERATION_CONFIG model=%s max_output_tokens=%s response_mime_type=%s temperature=%s attempt=%s",
                    model_name,
                    token_budget,
                    GEMINI_RESPONSE_MIME_TYPE,
                    GEMINI_TEMPERATURE,
                    attempt + 1,
                )
                response = await client.models.generate_content(
                    model=model_name,
                    contents=parts,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        max_output_tokens=token_budget,
                        temperature=GEMINI_TEMPERATURE,
                        response_mime_type=GEMINI_RESPONSE_MIME_TYPE,
                    ),
                )
                raw = response.text or ""
                finish_reason = response_finish_reason(response)
                response_token_count = response_output_token_count(response)
                logger.warning("RAW_GEMINI_RESPONSE=%s", raw)
                logger.warning("GEMINI_FINISH_REASON=%s", finish_reason)
                logger.warning("GEMINI_RESPONSE_TOKEN_COUNT=%s", response_token_count)
                logger.warning(
                    "GEMINI_RESPONSE_METADATA model=%s max_output_tokens=%s response_token_count=%s finish_reason=%s",
                    model_name,
                    token_budget,
                    response_token_count,
                    finish_reason,
                )
                if is_truncation_finish_reason(finish_reason) and attempt == 0:
                    token_budget *= GEMINI_TRUNCATION_RETRY_MULTIPLIER
                    logger.warning(
                        "GEMINI_RESPONSE_TRUNCATED finish_reason=%s retrying_with_max_output_tokens=%s",
                        finish_reason,
                        token_budget,
                    )
                    continue
                return parse_json_response(raw)

        raise ValueError("Gemini generation did not return a response")


def generate_template_blueprint(images: list[Path], prompt: str) -> dict:
    return GeminiProvider().generate_blueprint(images, prompt)


def parse_json_response(raw: str) -> dict:
    clean = raw.strip()
    direct_error: json.JSONDecodeError | None = None
    extracted_error: json.JSONDecodeError | None = None

    try:
        return json.loads(clean)
    except json.JSONDecodeError as exc:
        direct_error = exc

    if clean.startswith("```json"):
        clean = clean.removeprefix("```json").strip()
    if clean.startswith("```"):
        clean = clean.removeprefix("```").strip()
    if clean.endswith("```"):
        clean = clean.removesuffix("```").strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError as exc:
        extracted_error = exc

    for candidate in iter_json_object_candidates(clean):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            extracted_error = exc

    logger.error(
        "GEMINI_JSON_PARSE_ERROR direct=%s extracted=%s raw=%s",
        direct_error,
        extracted_error,
        raw,
    )
    if extracted_error:
        raise extracted_error
    if direct_error:
        raise direct_error
    raise ValueError("Gemini response did not contain a JSON object")


def iter_json_object_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start : index + 1])
                start = None

    if start is not None:
        logger.error(
            "GEMINI_JSON_EXTRACTION_INCOMPLETE start=%s length=%s likely_truncated=true",
            start,
            len(text),
        )
    return candidates


def response_finish_reason(response) -> str | None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    finish_reason = getattr(candidates[0], "finish_reason", None)
    if finish_reason is None:
        return None
    return getattr(finish_reason, "name", None) or str(finish_reason)


def response_output_token_count(response) -> int | None:
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        count = getattr(usage, "candidates_token_count", None)
        if count is not None:
            return count
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        return getattr(candidates[0], "token_count", None)
    return None


def is_truncation_finish_reason(finish_reason: str | None) -> bool:
    if not finish_reason:
        return False
    normalized = finish_reason.upper()
    return "MAX_TOKENS" in normalized or "TOKEN" in normalized or "LENGTH" in normalized


def fallback_blueprint() -> dict:
    from app.services.template_dsl_service import default_template_definition

    definition = default_template_definition(
        "Custom JD Template",
        "Generated conservative Wissen JD template after Gemini fallback",
    )
    value = definition.model_dump(mode="json")
    value.setdefault("metadata", {})["blueprint_confidence"] = 0.0
    return value


def _blueprint_confidence(value: dict) -> float | None:
    metadata = value.get("metadata") if isinstance(value, dict) else None
    if isinstance(metadata, dict):
        return metadata.get("blueprint_confidence")
    return None
