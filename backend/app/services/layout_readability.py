from __future__ import annotations

import re
from statistics import mean
from typing import Any, Sequence

from app.services.layout_similarity import ImageInput


MIN_BODY_FONT_PX = 11.0
MIN_HEADING_FONT_PX = 14.0
MIN_LINE_HEIGHT_RATIO = 1.35
MIN_CARD_PADDING_PX = 12.0


def compute_readability(rendered_html: str, rendered_images: Sequence[ImageInput]) -> dict[str, Any]:
    css = _extract_css(rendered_html)
    font_sizes = _extract_font_sizes(css)
    line_heights = _extract_line_heights(css)
    paddings = _extract_padding_values(css)
    whitespace_ratio = _estimate_image_whitespace(rendered_images)
    text_per_area_ratio = _estimate_text_per_area(rendered_html, rendered_images)
    content_compression_ratio = _estimate_content_compression(css)
    overflow_reasons = detect_overflow(rendered_html, css)
    clipping_reasons = detect_clipping(rendered_html, css, rendered_images)
    overflow_detected = bool(overflow_reasons)
    clipped_content_detected = bool(clipping_reasons)

    min_font_size = min(font_sizes) if font_sizes else 12.0
    avg_font_size = mean(font_sizes) if font_sizes else 12.0
    min_line_height = min(line_heights) if line_heights else 1.4
    min_padding = min(paddings) if paddings else 12.0
    card_density = _card_density_score(whitespace_ratio, text_per_area_ratio)

    score = 100.0
    if min_font_size < MIN_BODY_FONT_PX:
        score -= min(30.0, (MIN_BODY_FONT_PX - min_font_size) * 8)
    if avg_font_size < 12:
        score -= min(15.0, (12 - avg_font_size) * 5)
    if min_line_height < MIN_LINE_HEIGHT_RATIO:
        score -= min(18.0, (MIN_LINE_HEIGHT_RATIO - min_line_height) * 45)
    if min_padding < MIN_CARD_PADDING_PX:
        score -= min(12.0, (MIN_CARD_PADDING_PX - min_padding) * 2)
    if whitespace_ratio < 0.18:
        score -= min(20.0, (0.18 - whitespace_ratio) * 80)
    if text_per_area_ratio > 0.55:
        score -= min(18.0, (text_per_area_ratio - 0.55) * 60)
    if content_compression_ratio > 0.12:
        score -= min(18.0, content_compression_ratio * 100)
    if card_density > 0.75:
        score -= min(12.0, (card_density - 0.75) * 40)
    if overflow_detected:
        score -= 35.0
    if clipped_content_detected:
        score -= 35.0

    readability_score = round(max(0.0, min(100.0, score)), 2)
    return {
        "readability_score": readability_score,
        "min_font_size": round(min_font_size, 2),
        "avg_font_size": round(avg_font_size, 2),
        "line_height": round(min_line_height, 2),
        "card_density": round(card_density, 3),
        "whitespace_ratio": round(whitespace_ratio, 3),
        "text_per_area_ratio": round(text_per_area_ratio, 3),
        "content_compression_ratio": round(content_compression_ratio, 3),
        "overflow_detected": overflow_detected,
        "clipped_content_detected": clipped_content_detected,
        "overflow_reasons": overflow_reasons,
        "clipping_reasons": clipping_reasons,
        "clipping_reason": "; ".join(clipping_reasons),
    }


def detect_overflow(rendered_html: str, css: str | None = None) -> list[str]:
    css = css if css is not None else _extract_css(rendered_html)
    reasons: list[str] = []
    css_reason = _overflow_css_reason(css)
    if css_reason:
        reasons.append(css_reason)
    box_reason = _box_overflow_reason(rendered_html)
    if box_reason:
        reasons.append(box_reason)
    return reasons


def detect_clipping(rendered_html: str, css: str | None = None, rendered_images: Sequence[ImageInput] | None = None) -> list[str]:
    css = css if css is not None else _extract_css(rendered_html)
    reasons: list[str] = []
    css_reason = _clipping_css_reason(css)
    if css_reason:
        reasons.append(css_reason)
    if rendered_images is not None:
        edge_reason = _edge_clipping_reason(rendered_images)
        if edge_reason:
            reasons.append(edge_reason)
    return reasons


def _extract_css(rendered_html: str) -> str:
    matches = re.findall(r"<style[^>]*>(.*?)</style>", rendered_html, flags=re.IGNORECASE | re.DOTALL)
    return "\n".join(matches)


def _extract_font_sizes(css: str) -> list[float]:
    values = [_to_px(value, unit) for value, unit in re.findall(r"font-size\s*:\s*([0-9.]+)\s*(px|pt|em|rem|%)?", css, flags=re.IGNORECASE)]
    return [value for value in values if value > 0]


def _extract_line_heights(css: str) -> list[float]:
    values: list[float] = []
    for value, unit in re.findall(r"line-height\s*:\s*([0-9.]+)\s*(px|pt|em|rem|%)?", css, flags=re.IGNORECASE):
        parsed = float(value)
        if unit in {"px", "pt"}:
            values.append(parsed / 12.0)
        elif unit == "%":
            values.append(parsed / 100.0)
        else:
            values.append(parsed)
    return values


def _extract_padding_values(css: str) -> list[float]:
    values: list[float] = []
    for raw_value in re.findall(r"(?:padding|padding-top|padding-bottom|padding-left|padding-right)\s*:\s*([^;]+)", css, flags=re.IGNORECASE):
        for value, unit in re.findall(r"([0-9.]+)\s*(px|pt|em|rem|%)?", raw_value, flags=re.IGNORECASE):
            values.append(_to_px(value, unit))
    return [value for value in values if value > 0]


def _to_px(value: str, unit: str | None) -> float:
    parsed = float(value)
    normalized_unit = (unit or "px").lower()
    if normalized_unit == "pt":
        return parsed * 1.333
    if normalized_unit in {"em", "rem"}:
        return parsed * 16
    if normalized_unit == "%":
        return parsed / 100 * 16
    return parsed


def _estimate_image_whitespace(rendered_images: Sequence[ImageInput]) -> float:
    try:
        from PIL import Image
        from io import BytesIO
    except ImportError:
        return 0.25

    ratios: list[float] = []
    for image in rendered_images:
        data = image[1] if isinstance(image, tuple) else image
        if not isinstance(data, bytes):
            from pathlib import Path

            data = Path(data).read_bytes()
        with Image.open(BytesIO(data)) as opened:
            rgb = opened.convert("RGB").resize((120, max(1, int(120 * opened.height / max(opened.width, 1)))))
            pixels = list(rgb.getdata())
            white = sum(1 for pixel in pixels if pixel[0] > 245 and pixel[1] > 245 and pixel[2] > 245)
            ratios.append(white / max(len(pixels), 1))
    return mean(ratios) if ratios else 0.25


def _estimate_text_per_area(rendered_html: str, rendered_images: Sequence[ImageInput]) -> float:
    text = re.sub(r"<[^>]+>", " ", rendered_html)
    text_length = len(" ".join(text.split()))
    page_count = max(len(rendered_images), 1)
    return min(1.0, text_length / (page_count * 4200))


def _estimate_content_compression(css: str) -> float:
    penalties = 0.0
    penalties += len(re.findall(r"font-size\s*:\s*(?:[0-9.]+)\s*(?:px|pt)?", css, flags=re.IGNORECASE)) * 0.002
    penalties += len(re.findall(r"!important", css, flags=re.IGNORECASE)) * 0.01
    penalties += len(re.findall(r"(?:scale|zoom)\s*[:(]", css, flags=re.IGNORECASE)) * 0.04
    if "automatic single-page layout compression" in css:
        penalties += 0.25
    return min(1.0, penalties)


def _overflow_css_reason(css: str) -> str | None:
    if re.search(r"overflow(?:-[xy])?\s*:\s*(?:hidden|clip)", css, flags=re.IGNORECASE):
        return "text hidden by overflow"
    if re.search(r"text-overflow\s*:\s*ellipsis", css, flags=re.IGNORECASE):
        return "text hidden by ellipsis"
    if re.search(r"max-height\s*:[^;]+;\s*overflow(?:-[xy])?\s*:\s*(?:hidden|clip)", css, flags=re.IGNORECASE | re.DOTALL):
        return "content outside container hidden by max-height"
    return None


def _clipping_css_reason(css: str) -> str | None:
    if re.search(r"clip-path\s*:", css, flags=re.IGNORECASE):
        return "content clipped by clip-path"
    if re.search(r"overflow(?:-[xy])?\s*:\s*clip", css, flags=re.IGNORECASE):
        return "content clipped by overflow: clip"
    if re.search(r"height\s*:[^;]+;\s*overflow(?:-[xy])?\s*:\s*(?:hidden|clip)", css, flags=re.IGNORECASE | re.DOTALL):
        return "content hidden by fixed height and overflow"
    return None


def _box_overflow_reason(rendered_html: str) -> str | None:
    try:
        from weasyprint import HTML

        document = HTML(string=rendered_html).render()
    except Exception:
        return None
    for page in document.pages:
        page_box = getattr(page, "_page_box", None)
        if page_box is None:
            continue
        page_width = float(getattr(page, "width", None) or getattr(page_box, "width", 0) or 0)
        page_height = float(getattr(page, "height", None) or getattr(page_box, "height", 0) or 0)
        for box in _walk_boxes(page_box):
            x = float(getattr(box, "position_x", 0) or 0)
            y = float(getattr(box, "position_y", 0) or 0)
            width = float(getattr(box, "width", 0) or 0)
            height = float(getattr(box, "height", 0) or 0)
            if x < -2 or y < -2 or x + width > page_width + 2 or y + height > page_height + 2:
                tag = getattr(box, "element_tag", None) or type(box).__name__
                return f"element exceeds page bounds: {tag} x={round(x, 2)} y={round(y, 2)} w={round(width, 2)} h={round(height, 2)} page_w={round(page_width, 2)} page_h={round(page_height, 2)}"
    return None


def _walk_boxes(box: Any) -> list[Any]:
    boxes = [box]
    for child in getattr(box, "children", []) or []:
        boxes.extend(_walk_boxes(child))
    return boxes


def _edge_clipping_reason(rendered_images: Sequence[ImageInput]) -> str | None:
    try:
        from PIL import Image
        from io import BytesIO
    except ImportError:
        return None

    for index, image in enumerate(rendered_images, start=1):
        data = image[1] if isinstance(image, tuple) else image
        if not isinstance(data, bytes):
            from pathlib import Path

            data = Path(data).read_bytes()
        with Image.open(BytesIO(data)) as opened:
            rgb = opened.convert("RGB")
            width, height = rgb.size
            edge = max(2, min(width, height) // 100)
            bands = [
                rgb.crop((0, height - edge, width, height)),
                rgb.crop((0, 0, edge, height)),
                rgb.crop((width - edge, 0, width, height)),
            ]
            for band in bands:
                pixels = list(band.getdata())
                non_white = sum(1 for pixel in pixels if not (pixel[0] > 245 and pixel[1] > 245 and pixel[2] > 245))
                edge_density = non_white / max(len(pixels), 1)
                if 0.12 < edge_density < 0.65:
                    return f"screenshot analysis threshold exceeded: page={index} edge_density={round(edge_density, 3)}"
    return None


def _card_density_score(whitespace_ratio: float, text_per_area_ratio: float) -> float:
    return max(0.0, min(1.0, (1.0 - whitespace_ratio) * 0.7 + text_per_area_ratio * 0.3))
