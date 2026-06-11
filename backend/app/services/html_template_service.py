import json
import logging
import tempfile
import re
from copy import deepcopy
from datetime import datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Sequence

from app.core.config import settings
from app.llm.base import LLMProvider
from app.services.layout_readability import compute_readability
from app.services.layout_similarity import compute_similarity
from app.services.pdf_image_service import convert_pdf_to_png_images

logger = logging.getLogger(__name__)

ALLOWED_TEMPLATE_FIELDS = {
    "title",
    "job_summary",
    "roles_and_responsibilities",
    "required_skills",
    "preferred_skills",
    "qualifications",
    "experience",
    "location",
    "employment_type",
    "department",
    "salary_range",
    "benefits",
    "technical_skills",
    "soft_skills",
    "education",
    "certifications",
    "selection_process",
    "additional_information",
    "contact_information",
    "about_company",
}

ALLOWED_HTML_TAGS = {
    "article",
    "aside",
    "b",
    "br",
    "div",
    "em",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "i",
    "li",
    "main",
    "ol",
    "p",
    "section",
    "small",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
VOID_TAGS = {"br", "hr"}
ALLOWED_ATTRS = {"class", "id", "role", "aria-label", "colspan", "rowspan"}
DANGEROUS_HTML_TAGS = {"script", "iframe", "object", "embed", "link", "meta", "base", "form", "input", "button"}
DANGEROUS_CSS_PATTERNS = (
    r"@import\b",
    r"url\s*\(",
    r"expression\s*\(",
    r"javascript\s*:",
    r"vbscript\s*:",
    r"behavior\s*:",
    r"-moz-binding\s*:",
)

HTML_TEMPLATE_SYSTEM_PROMPT = f"""You convert uploaded JD PDF page images into a reusable HTML/CSS template.
Return ONLY valid JSON:
{{
  "html": "...",
  "css": "...",
  "mapped_fields": ["title", "job_summary"],
  "layout_metadata": {{
    "page_count": 1,
    "layout_type": "single_page",
    "visual_density": "high",
    "regions": [
      {{"name": "header", "x_pct": 0, "y_pct": 0, "width_pct": 100, "height_pct": 18}},
      {{"name": "sidebar", "x_pct": 0, "y_pct": 18, "width_pct": 30, "height_pct": 72}},
      {{"name": "main", "x_pct": 30, "y_pct": 18, "width_pct": 70, "height_pct": 72}},
      {{"name": "footer", "x_pct": 0, "y_pct": 90, "width_pct": 100, "height_pct": 10}}
    ]
  }}
}}

The uploaded PDF is NOT content. It is ONLY a visual design reference.

PRIMARY OBJECTIVE:
Reconstruct the page composition and layout structure of the uploaded PDF.

This is a page-layout template, not a generic article. Preserve:
- page regions and visual orientation
- region boundaries with approximate x/y/width/height percentages
- hero/header areas
- content block placement
- section heights and width ratios
- card dimensions
- spacing relationships
- visual hierarchy
- page density
- whether the template is intended to fit on one page or multiple pages
- pagination intent and content distribution

Generate layout-first HTML:
- Use a top-level page container such as <div class="template-page layout-single-page">.
- Use semantic regions: header, aside.sidebar, main, footer, section.
- Use CSS Grid/Flexbox for page regions, sidebars, metadata grids, cards, and balanced columns.
- Use explicit sizing where needed: min-height, grid-template-columns, grid-template-rows, gap, padding, max-height.
- For a one-page reference, design the CSS so normal JD content fits on one page when possible.
- Prefer compact reusable regions over long vertical stacks.
- Include layout_metadata.regions for the major visible regions. Coordinates must be percentages of each page.
- Uploaded page count is a preference, not a hard limit. If realistic JD content needs more space, allow extra pages.
- Preserve recruiter-grade readability over strict page-count matching.
- Body text must not be smaller than 11px.
- Section headings must not be smaller than 14px.
- Line-height must not be below 1.35.
- Card/panel padding must not be below 12px.
- Do not hide overflowing content. Avoid overflow: hidden, text-overflow: ellipsis, fixed max-height clipping, and CSS transforms that shrink content.
- Skills, qualifications, benefits, and list-heavy sections must use adaptive layouts that can collapse from two columns to one column when content is imbalanced.

Avoid:
- long article-style vertical stacks
- generic <header><section><section><section> composition
- unnecessary nested sections
- huge nested tables
- letting every section expand as normal document flow when the reference is a fixed layout
- aggressively compressing content just to fit the uploaded page count

Use tables only when the visual design has a true table or label/value grid.

The HTML must use Jinja2 placeholders for runtime JD data. Example:
<header class="hero"><h1>{{{{ title }}}}</h1></header>
<section class="summary">{{{{ job_summary }}}}</section>

Allowed placeholders:
{", ".join(sorted(ALLOWED_TEMPLATE_FIELDS))}

Rules:
- Do not copy job description body text from the uploaded PDF.
- Treat visible PDF text as placeholder labels only.
- Replace uploaded-brand specifics with Wissen-compatible neutral branding.
- Do not include <script>, <iframe>, external URLs, JavaScript, forms, or remote assets.
- Do not include markdown fences.
- Keep CSS self-contained and print-friendly for WeasyPrint.
- Use @page for page size/margins.
- Return reusable HTML and CSS only, not a complete PDF.
- Do not generate Python code, renderer code, or implementation instructions.
- mapped_fields must list every placeholder used in html."""


def build_html_template_user_prompt(filename: str, page_count: int) -> str:
    return (
        f"Uploaded reference PDF filename: {filename}\n"
        f"Rendered PDF pages provided as images: {page_count}\n\n"
        "Create a reusable HTML/CSS template for future Wissen job descriptions. "
        "The uploaded PDF is a visual layout reference only; use placeholders for JD data. "
        "Preserve page composition, region sizing, density, and pagination intent."
    )


async def generate_html_template(
    *,
    llm: LLMProvider,
    filename: str,
    page_images: Sequence[tuple[str, bytes, str]],
) -> dict[str, Any]:
    result = await request_html_template_generation(llm=llm, filename=filename, page_images=page_images)
    candidate = build_template_candidate(result, len(page_images))
    best_candidate = score_template_candidate(candidate, page_images)

    for iteration in range(1, 3):
        if is_acceptable_template(best_candidate["template_quality_score"]):
            break
        logger.warning("REPAIR_ITERATION=%s", iteration)
        try:
            repaired = await request_html_template_repair(
                llm=llm,
                filename=filename,
                page_images=page_images,
                rendered_images=best_candidate.get("_rendered_images") or [],
                candidate=best_candidate,
                diagnostics=best_candidate["template_quality_score"],
                iteration=iteration,
            )
            repaired_candidate = build_template_candidate(repaired, len(page_images))
            repaired_candidate = score_template_candidate(repaired_candidate, page_images)
        except Exception as exc:
            if is_transient_llm_error(exc):
                logger.warning(
                    "TEMPLATE_REPAIR_TRANSIENT_FAILURE iteration=%s best_score=%s storing_best_template error=%r",
                    iteration,
                    best_candidate["template_quality_score"].get("final_template_score"),
                    exc,
                )
                best_candidate["template_quality_score"]["status"] = "needs_review"
                best_candidate["template_quality_score"]["review_reason"] = "Gemini repair failed with a transient error"
                break
            logger.warning("TEMPLATE_REPAIR_FAILED iteration=%s error=%r", iteration, exc)
            continue
        if is_better_template(repaired_candidate["template_quality_score"], best_candidate["template_quality_score"]):
            best_candidate = repaired_candidate

    quality_score = best_candidate["template_quality_score"]
    final_score = float(quality_score.get("final_template_score") or 0)
    logger.warning("FINAL_TEMPLATE_SCORE=%s", final_score)
    if quality_score.get("overflow_detected") or quality_score.get("clipped_content_detected") or float(quality_score.get("readability_score") or 0) < 70:
        quality_score["status"] = "needs_review"
        quality_score["review_reason"] = determine_review_reason(quality_score)
        save_validation_debug_artifacts(page_images, best_candidate.get("_rendered_images") or [], quality_score)
        logger.warning(
            "TEMPLATE_STORED_NEEDS_REVIEW final_score=%s readability_score=%s reason=%s",
            final_score,
            quality_score.get("readability_score"),
            quality_score.get("review_reason"),
        )
    else:
        quality_score.setdefault("status", "accepted")
    if float(quality_score.get("readability_score") or 0) < 80:
        logger.warning("TEMPLATE_ACCEPTED_WITH_READABILITY_WARNING readability_score=%s", quality_score.get("readability_score"))

    best_candidate.pop("_rendered_images", None)
    logger.warning("TEMPLATE_HTML_LENGTH=%s", len(best_candidate["html"]))
    logger.warning("TEMPLATE_CSS_LENGTH=%s", len(best_candidate["css"]))
    logger.warning("MAPPED_FIELDS=%s", best_candidate["mapped_fields"])
    return best_candidate


async def request_html_template_generation(
    *,
    llm: LLMProvider,
    filename: str,
    page_images: Sequence[tuple[str, bytes, str]],
) -> dict[str, Any]:
    result = await llm.complete_json_with_images(
        system=HTML_TEMPLATE_SYSTEM_PROMPT,
        user=build_html_template_user_prompt(filename, len(page_images)),
        images=page_images,
        max_tokens=9000,
    )
    return unwrap_template_result(result)


async def request_html_template_repair(
    *,
    llm: LLMProvider,
    filename: str,
    page_images: Sequence[tuple[str, bytes, str]],
    rendered_images: Sequence[tuple[str, bytes, str]],
    candidate: dict[str, Any],
    diagnostics: dict[str, Any],
    iteration: int,
) -> dict[str, Any]:
    repair_prompt = (
        "The rendered result does not match the uploaded reference layout closely enough.\n\n"
        f"Reference filename: {filename}\n"
        f"Repair iteration: {iteration}\n"
        f"Diagnostics JSON:\n{json.dumps(diagnostics, ensure_ascii=True)}\n\n"
        "Current HTML:\n"
        f"{candidate['html']}\n\n"
        "Current CSS:\n"
        f"{candidate['css']}\n\n"
        "Return improved JSON with html, css, mapped_fields, and layout_metadata only. "
        "Preserve visual composition, region proportions, width ratios, density, and header/footer placement. "
        "Do not shrink body text below 11px, headings below 14px, line-height below 1.35, or card padding below 12px. "
        "Do not use overflow:hidden, clipped max-height regions, ellipsis, transforms, or aggressive compression. "
        "If content does not fit, allow additional pages. Prefer readable adaptive CSS Grid/Flexbox layouts that "
        "collapse list-heavy two-column sections to one column when needed."
    )
    repair_images = [
        *[(f"reference-{name}", data, mime_type) for name, data, mime_type in page_images],
        *[(f"rendered-{name}", data, mime_type) for name, data, mime_type in rendered_images],
    ]
    result = await llm.complete_json_with_images(
        system=HTML_TEMPLATE_SYSTEM_PROMPT,
        user=repair_prompt,
        images=repair_images,
        max_tokens=11000,
    )
    return unwrap_template_result(result)


def unwrap_template_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict) and "template" in result and isinstance(result["template"], dict):
        result = result["template"]
    if not isinstance(result, dict):
        raise ValueError("HTML template response was not a JSON object")
    return result


def build_template_candidate(result: dict[str, Any], uploaded_page_count: int) -> dict[str, Any]:
    html = sanitize_template_html(str(result.get("html") or ""))
    css = enforce_readability_css(sanitize_template_css(str(result.get("css") or "")))
    mapped_fields = normalize_mapped_fields(result.get("mapped_fields"), html)
    layout_metadata = normalize_layout_metadata(result.get("layout_metadata"), uploaded_page_count, html)
    validate_html_template(html, css, mapped_fields)
    return {"html": html, "css": css, "mapped_fields": mapped_fields, "layout_metadata": layout_metadata}


def score_template_candidate(
    candidate: dict[str, Any],
    reference_images: Sequence[tuple[str, bytes, str]],
) -> dict[str, Any]:
    scored = deepcopy(candidate)
    stress_results = render_stress_test_results(scored["html"], scored["css"], scored["mapped_fields"])
    rendered_images = stress_results["medium"]["images"]
    diagnostics = compute_similarity(reference_images, rendered_images)
    readability = combine_readability_results([result["readability"] for result in stress_results.values()])
    final_score = compute_template_quality_score(diagnostics, readability)
    logger.warning("REFERENCE_PAGE_COUNT=%s", diagnostics.get("reference_page_count"))
    logger.warning("RENDERED_PAGE_COUNT=%s", diagnostics.get("rendered_page_count"))
    logger.warning("PAGE_COUNT_MATCH=%s", diagnostics.get("page_count_match"))
    logger.warning("LAYOUT_SIMILARITY=%s", diagnostics.get("similarity_score"))
    logger.warning("SIMILARITY_SCORE=%s", diagnostics.get("similarity_score"))
    logger.warning("READABILITY_SCORE=%s", readability.get("readability_score"))
    logger.warning("MIN_FONT_SIZE=%s", readability.get("min_font_size"))
    logger.warning("AVG_FONT_SIZE=%s", readability.get("avg_font_size"))
    logger.warning("OVERFLOW_DETECTED=%s", readability.get("overflow_detected"))
    logger.warning("CLIPPED_CONTENT_DETECTED=%s", readability.get("clipped_content_detected"))
    logger.warning("OVERFLOW_REASON=%s", readability.get("overflow_reasons"))
    logger.warning("CLIPPING_REASON=%s", readability.get("clipping_reasons"))
    logger.warning("REGION_MATCH=%s", diagnostics.get("region_match"))
    logger.warning("DENSITY_MATCH=%s", diagnostics.get("density_match"))
    logger.warning("COLOR_MATCH=%s", diagnostics.get("color_match"))

    scored["layout_metadata"] = {
        **scored["layout_metadata"],
        "uploaded_page_count": len(reference_images),
        "rendered_page_count": diagnostics.get("rendered_page_count"),
        "page_count_match": diagnostics.get("page_count_match"),
    }
    scored["template_quality_score"] = {
        **diagnostics,
        **readability,
        "final_template_score": final_score,
        "stress_tests": {
            name: {
                "page_count": len(result["images"]),
                "readability_score": result["readability"].get("readability_score"),
                "overflow_detected": result["readability"].get("overflow_detected"),
                "clipped_content_detected": result["readability"].get("clipped_content_detected"),
                "overflow_reasons": result["readability"].get("overflow_reasons"),
                "clipping_reasons": result["readability"].get("clipping_reasons"),
            }
            for name, result in stress_results.items()
        },
    }
    scored["_rendered_images"] = rendered_images
    return scored


def is_acceptable_template(quality_score: dict[str, Any]) -> bool:
    return (
        float(quality_score.get("readability_score") or 0) >= 80
        and float(quality_score.get("final_template_score") or 0) >= 80
        and not quality_score.get("overflow_detected")
        and not quality_score.get("clipped_content_detected")
    )


def is_better_template(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    candidate_safe = not candidate.get("overflow_detected") and not candidate.get("clipped_content_detected")
    current_safe = not current.get("overflow_detected") and not current.get("clipped_content_detected")
    if candidate_safe != current_safe:
        return candidate_safe
    candidate_readability = float(candidate.get("readability_score") or 0)
    current_readability = float(current.get("readability_score") or 0)
    if abs(candidate_readability - current_readability) >= 5:
        return candidate_readability > current_readability
    return float(candidate.get("final_template_score") or 0) > float(current.get("final_template_score") or 0)


def is_transient_llm_error(exc: Exception) -> bool:
    text = str(exc)
    return any(code in text for code in ("429", "500", "502", "503", "504"))


def determine_review_reason(quality_score: dict[str, Any]) -> str:
    reasons = []
    if quality_score.get("overflow_detected"):
        reasons.append(f"overflow: {quality_score.get('overflow_reasons')}")
    if quality_score.get("clipped_content_detected"):
        reasons.append(f"clipping: {quality_score.get('clipping_reasons')}")
    if float(quality_score.get("readability_score") or 0) < 70:
        reasons.append(f"readability_score below 70: {quality_score.get('readability_score')}")
    return "; ".join(reasons) or "quality score requires admin review"


def save_validation_debug_artifacts(
    reference_images: Sequence[tuple[str, bytes, str]],
    rendered_images: Sequence[tuple[str, bytes, str]],
    quality_score: dict[str, Any],
) -> None:
    if not reference_images or not rendered_images:
        return
    debug_dir = Path(settings.UPLOADS_DIR) / "template-validation-debug" / datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        reference_path = debug_dir / "reference.png"
        rendered_path = debug_dir / "rendered.png"
        overlay_path = debug_dir / "clipping-overlay.png"
        reference_path.write_bytes(reference_images[0][1])
        rendered_path.write_bytes(rendered_images[0][1])
        create_clipping_overlay(rendered_images[0][1], overlay_path, quality_score)
        quality_path = debug_dir / "quality-score.json"
        quality_path.write_text(json.dumps(quality_score, ensure_ascii=True, indent=2), encoding="utf-8")
        quality_score["debug_artifacts"] = {
            "reference": str(reference_path),
            "rendered": str(rendered_path),
            "clipping_overlay": str(overlay_path),
            "quality_score": str(quality_path),
        }
        logger.warning(
            "TEMPLATE_VALIDATION_DEBUG_ARTIFACTS reference=%s rendered=%s clipping_overlay=%s",
            reference_path,
            rendered_path,
            overlay_path,
        )
    except Exception as exc:
        logger.warning("TEMPLATE_VALIDATION_DEBUG_ARTIFACTS_FAILED error=%r", exc)


def create_clipping_overlay(rendered_image: bytes, output_path: Path, quality_score: dict[str, Any]) -> None:
    try:
        from io import BytesIO

        from PIL import Image, ImageDraw
    except ImportError:
        output_path.write_bytes(rendered_image)
        return

    with Image.open(BytesIO(rendered_image)) as opened:
        image = opened.convert("RGB")
        draw = ImageDraw.Draw(image)
        width, height = image.size
        edge = max(4, min(width, height) // 100)
        color = (220, 30, 30)
        draw.rectangle((0, 0, width - 1, height - 1), outline=color, width=edge)
        y = edge + 8
        for reason in (quality_score.get("clipping_reasons") or quality_score.get("overflow_reasons") or [])[:4]:
            draw.text((edge + 8, y), str(reason)[:140], fill=color)
            y += 22
        image.save(output_path)


def compute_template_quality_score(similarity: dict[str, Any], readability: dict[str, Any]) -> float:
    score = (
        (0.40 * float(readability.get("readability_score") or 0))
        + (0.25 * float(similarity.get("similarity_score") or 0))
        + (0.20 * float(similarity.get("region_match") or 0) * 100)
        + (0.15 * float(similarity.get("color_match") or 0) * 100)
    )
    return round(max(0.0, min(100.0, score)), 2)


def combine_readability_results(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {
            "readability_score": 0,
            "min_font_size": 0,
            "avg_font_size": 0,
            "overflow_detected": True,
            "clipped_content_detected": True,
            "overflow_reasons": ["readability analysis did not run"],
            "clipping_reasons": ["readability analysis did not run"],
        }
    return {
        "readability_score": round(min(float(result.get("readability_score") or 0) for result in results), 2),
        "min_font_size": round(min(float(result.get("min_font_size") or 0) for result in results), 2),
        "avg_font_size": round(sum(float(result.get("avg_font_size") or 0) for result in results) / len(results), 2),
        "line_height": round(min(float(result.get("line_height") or 0) for result in results), 2),
        "card_density": round(max(float(result.get("card_density") or 0) for result in results), 3),
        "whitespace_ratio": round(min(float(result.get("whitespace_ratio") or 0) for result in results), 3),
        "text_per_area_ratio": round(max(float(result.get("text_per_area_ratio") or 0) for result in results), 3),
        "content_compression_ratio": round(max(float(result.get("content_compression_ratio") or 0) for result in results), 3),
        "overflow_detected": any(bool(result.get("overflow_detected")) for result in results),
        "clipped_content_detected": any(bool(result.get("clipped_content_detected")) for result in results),
        "overflow_reasons": [
            reason
            for result in results
            for reason in (result.get("overflow_reasons") or [])
        ],
        "clipping_reasons": [
            reason
            for result in results
            for reason in (result.get("clipping_reasons") or [])
        ],
    }


def validate_html_template(html: str, css: str, mapped_fields: list[str]) -> None:
    if not html.strip():
        raise ValueError("Generated HTML template is empty")
    if not css.strip():
        raise ValueError("Generated CSS template is empty")
    placeholders = extract_placeholders(html)
    if not placeholders:
        raise ValueError("Generated HTML template has no placeholders")
    if len(mapped_fields) < 3:
        raise ValueError(f"Generated HTML template mapped fewer than 3 fields: {mapped_fields}")
    unknown = sorted(set(placeholders) - ALLOWED_TEMPLATE_FIELDS)
    if unknown:
        raise ValueError(f"Generated HTML template used unsupported placeholders: {unknown}")


def normalize_layout_metadata(raw_metadata: Any, uploaded_page_count: int, html: str) -> dict[str, Any]:
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    expected_pages = coerce_positive_int(metadata.get("page_count") or metadata.get("expected_pages"), uploaded_page_count)
    primary_regions = metadata.get("primary_regions")
    if not isinstance(primary_regions, list):
        primary_regions = detect_primary_regions(html)
    regions = normalize_layout_regions(metadata.get("regions"), primary_regions)
    normalized = {
        "page_count": expected_pages,
        "expected_pages": expected_pages,
        "layout_type": str(metadata.get("layout_type") or ("single_page" if expected_pages == 1 else "multi_page")),
        "visual_density": str(metadata.get("visual_density") or ("high" if expected_pages == 1 else "medium")),
        "primary_regions": [str(region) for region in primary_regions if str(region).strip()],
        "regions": regions,
    }
    return normalized


def normalize_layout_regions(raw_regions: Any, fallback_regions: Any) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    if isinstance(raw_regions, list):
        for region in raw_regions:
            if not isinstance(region, dict):
                continue
            name = str(region.get("name") or "").strip()
            if not name:
                continue
            regions.append(
                {
                    "name": name,
                    "x_pct": clamp_percent(region.get("x_pct"), 0),
                    "y_pct": clamp_percent(region.get("y_pct"), 0),
                    "width_pct": clamp_percent(region.get("width_pct"), 100),
                    "height_pct": clamp_percent(region.get("height_pct"), 20),
                }
            )
    if regions:
        return regions
    if isinstance(fallback_regions, list) and fallback_regions:
        height = 100 / max(len(fallback_regions), 1)
        return [
            {
                "name": str(region),
                "x_pct": 0,
                "y_pct": round(index * height, 2),
                "width_pct": 100,
                "height_pct": round(height, 2),
            }
            for index, region in enumerate(fallback_regions)
            if str(region).strip()
        ]
    return [{"name": "main", "x_pct": 0, "y_pct": 0, "width_pct": 100, "height_pct": 100}]


def validate_and_optimize_layout(
    *,
    html: str,
    css: str,
    mapped_fields: list[str],
    layout_metadata: dict[str, Any],
    uploaded_page_count: int,
) -> tuple[str, str, dict[str, Any]]:
    diagnostics = render_layout_diagnostics(html, css, mapped_fields)
    expected_pages = int(layout_metadata.get("expected_pages") or uploaded_page_count or 1)
    logger.warning("DETECTED_PAGE_COUNT=%s", uploaded_page_count)
    logger.warning("EXPECTED_PAGE_COUNT=%s", expected_pages)
    logger.warning("ACTUAL_PAGE_COUNT=%s", diagnostics.get("actual_page_count"))
    logger.warning("MAJOR_REGIONS_DETECTED=%s", layout_metadata.get("primary_regions"))
    logger.warning("RENDERED_REGION_COUNT=%s", diagnostics.get("rendered_region_count"))
    logger.warning("WHITESPACE_RATIO=%s", diagnostics.get("whitespace_ratio"))
    logger.warning("SECTION_HEIGHTS=%s", diagnostics.get("section_heights"))

    layout_metadata = {
        **layout_metadata,
        "uploaded_page_count": uploaded_page_count,
        "actual_page_count": diagnostics.get("actual_page_count"),
        "rendered_region_count": diagnostics.get("rendered_region_count"),
        "whitespace_ratio": diagnostics.get("whitespace_ratio"),
        "section_heights": diagnostics.get("section_heights"),
        "layout_optimized": False,
    }
    return html, css, layout_metadata


def render_layout_diagnostics(html: str, css: str, mapped_fields: list[str]) -> dict[str, Any]:
    rendered_html = render_template_preview_html(html, css, mapped_fields)
    actual_page_count = None
    whitespace_ratio = None
    try:
        from weasyprint import HTML

        document = HTML(string=rendered_html, base_url=str(Path(tempfile.gettempdir()).resolve())).render()
        actual_page_count = len(document.pages)
        whitespace_ratio = estimate_whitespace_ratio(rendered_html)
    except Exception as exc:
        logger.warning("LAYOUT_DIAGNOSTICS_RENDER_FAILED error=%r", exc)
    return {
        "actual_page_count": actual_page_count or 0,
        "rendered_region_count": count_rendered_regions(rendered_html),
        "whitespace_ratio": whitespace_ratio,
        "section_heights": extract_css_section_heights(css),
    }


def render_template_candidate_images(
    html: str,
    css: str,
    mapped_fields: list[str],
) -> list[tuple[str, bytes, str]]:
    return render_template_candidate_result(html, css, mapped_fields, *sample_template_data("medium"))["images"]


def render_stress_test_results(
    html: str,
    css: str,
    mapped_fields: list[str],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for size in ("small", "medium", "large"):
        sample_data, sample_metadata = sample_template_data(size)
        rendered = render_template_candidate_result(html, css, mapped_fields, sample_data, sample_metadata)
        rendered["readability"] = compute_readability(rendered["rendered_html"], rendered["images"])
        logger.warning(
            "CONTENT_STRESS_TEST size=%s page_count=%s readability_score=%s overflow_detected=%s clipped_content_detected=%s",
            size,
            len(rendered["images"]),
            rendered["readability"].get("readability_score"),
            rendered["readability"].get("overflow_detected"),
            rendered["readability"].get("clipped_content_detected"),
        )
        results[size] = rendered
    return results


def render_template_candidate_result(
    html: str,
    css: str,
    mapped_fields: list[str],
    sample_data: dict[str, Any],
    sample_metadata: dict[str, Any],
) -> dict[str, Any]:
    from app.services.html_template_renderer import HtmlTemplateRenderer

    with tempfile.TemporaryDirectory(prefix="jd-template-render-") as temp_dir:
        temp_path = Path(temp_dir)
        pdf_path = temp_path / "candidate.pdf"
        renderer = HtmlTemplateRenderer(html, css, mapped_fields)
        title = str(sample_data.get("title") or "Senior Java Backend Engineer")
        rendered_html = renderer.render_html(title, sample_data, sample_metadata)
        renderer.render_pdf(pdf_path, title, sample_data, sample_metadata)
        images = convert_pdf_to_png_images(pdf_path.read_bytes(), temp_path / "pages")
        return {"images": images, "rendered_html": rendered_html}


def render_template_preview_html(html: str, css: str, mapped_fields: list[str]) -> str:
    from app.services.html_template_renderer import HtmlTemplateRenderer

    sample_data, sample_metadata = sample_template_data("medium")
    return HtmlTemplateRenderer(html, css, mapped_fields).render_html(
        "Senior Java Backend Engineer",
        sample_data,
        sample_metadata,
    )


def sample_template_data(size: str = "medium") -> tuple[dict[str, Any], dict[str, Any]]:
    base_data = {
        "title": "Senior Java Backend Engineer",
        "job_summary": "Design and deliver scalable enterprise platforms with clear ownership, production quality, and strong collaboration across teams.",
        "roles_and_responsibilities": [
            "Lead design and implementation of business-critical services.",
            "Collaborate with product, QA, and delivery stakeholders.",
            "Improve reliability, performance, and engineering standards.",
        ],
        "responsibilities": [
            "Lead design and implementation of business-critical services.",
            "Collaborate with product, QA, and delivery stakeholders.",
            "Improve reliability, performance, and engineering standards.",
        ],
        "required_skills": ["Java", "Spring Boot", "Microservices", "REST APIs", "SQL"],
        "requirements": ["Java", "Spring Boot", "Microservices", "REST APIs", "SQL"],
        "preferred_skills": ["AWS", "Docker", "Kubernetes"],
        "nice_to_have": ["AWS", "Docker", "Kubernetes"],
        "technical_skills": ["Java", "Spring Boot", "Microservices", "SQL", "Hibernate"],
        "soft_skills": ["Communication", "Ownership", "Collaboration"],
        "qualifications": ["B.Tech or equivalent engineering degree", "Strong backend engineering fundamentals"],
        "about_company": "Wissen Technology builds high-impact software products for global clients.",
        "education": "B.Tech / B.E. / MCA or equivalent",
        "experience": "5 to 8 Years",
        "location": "Bengaluru",
        "employment_type": "Full Time",
        "department": "Engineering",
        "salary_range": "As per company standards",
        "benefits": ["Health insurance", "Learning programs", "Flexible hybrid work"],
        "certifications": ["AWS certification preferred"],
        "selection_process": ["Technical screening", "Architecture discussion", "Managerial round"],
        "additional_information": "Candidates should be comfortable owning production services.",
        "contact_information": "careers@wissen.com",
    }
    if size == "small":
        base_data["job_summary"] = "Build reliable backend services for enterprise platforms."
        base_data["roles_and_responsibilities"] = base_data["roles_and_responsibilities"][:2]
        base_data["responsibilities"] = base_data["responsibilities"][:2]
        base_data["required_skills"] = base_data["required_skills"][:3]
        base_data["requirements"] = base_data["requirements"][:3]
        base_data["technical_skills"] = base_data["technical_skills"][:3]
        base_data["benefits"] = base_data["benefits"][:2]
    elif size == "large":
        base_data["job_summary"] = (
            "Wissen Technology is hiring a senior backend engineer to design, modernize, and operate scalable "
            "enterprise platforms. The role requires hands-on service ownership, API design, distributed systems "
            "thinking, observability, performance tuning, and production-quality engineering. The engineer will "
            "work closely with product, QA, DevOps, architects, and client stakeholders to deliver measurable "
            "business outcomes while improving engineering standards across the team."
        )
        base_data["roles_and_responsibilities"] = [
            "Design and build resilient Java and Spring Boot services for high-volume enterprise workflows.",
            "Own API contracts, service boundaries, production readiness, and operational quality.",
            "Collaborate with product managers, QA engineers, architects, and DevOps teams across delivery cycles.",
            "Improve reliability, performance, tracing, observability, and incident response practices.",
            "Review technical designs, mentor engineers, and raise code quality through disciplined reviews.",
            "Translate business requirements into maintainable backend components and integration patterns.",
            "Contribute to deployment automation, environment readiness, and release governance.",
            "Identify technical debt and propose pragmatic modernization plans.",
        ]
        base_data["responsibilities"] = base_data["roles_and_responsibilities"]
        base_data["required_skills"] = [
            "Core Java", "Java 8+", "Spring Boot", "Spring MVC", "REST APIs", "Microservices",
            "SQL", "NoSQL", "Hibernate", "JUnit", "Kafka", "System Design",
        ]
        base_data["requirements"] = [
            "Strong expertise in Core Java, Java 8+, collections, concurrency, and backend design patterns.",
            "Hands-on experience building REST APIs and microservices using Spring Boot and Spring MVC.",
            "Working knowledge of SQL and NoSQL databases, schema design, and query optimization.",
            "Experience with unit testing, integration testing, code reviews, and CI/CD practices.",
            "Good understanding of distributed systems, observability, logging, tracing, and performance tuning.",
            "Ability to design reliable integrations with internal platforms and third-party systems.",
            "Familiarity with secure coding, authentication patterns, and production support practices.",
            "Comfortable working in agile delivery environments with cross-functional stakeholders.",
        ]
        base_data["preferred_skills"] = ["AWS", "Docker", "Kubernetes", "Kafka", "Redis", "Terraform"]
        base_data["nice_to_have"] = base_data["preferred_skills"]
        base_data["technical_skills"] = base_data["required_skills"]
        base_data["soft_skills"] = ["Clear communication", "Ownership", "Mentoring", "Stakeholder collaboration", "Analytical thinking"]
        base_data["qualifications"] = [
            "B.Tech, B.E., MCA, or equivalent engineering degree.",
            "5 to 8 years of backend engineering experience.",
            "Experience delivering production-grade systems in enterprise environments.",
            "Ability to work independently while coordinating across distributed teams.",
        ]
        base_data["benefits"] = ["Health insurance", "Learning programs", "Flexible hybrid work", "Paid time off", "Career growth programs"]
    sample_metadata = {
        "experience_years": "5 to 8 Years",
        "location": "Bengaluru",
        "employment_type": "Full Time",
        "department": "Engineering",
    }
    return base_data, sample_metadata


def detect_primary_regions(html: str) -> list[str]:
    regions = []
    for tag in ("header", "aside", "main", "footer", "section"):
        if re.search(rf"<{tag}\b", html, flags=re.IGNORECASE):
            regions.append("sidebar" if tag == "aside" else tag)
    return regions or ["main"]


def count_rendered_regions(html: str) -> int:
    return len(re.findall(r"<(?:header|aside|main|footer|section|article)\b", html, flags=re.IGNORECASE))


def estimate_whitespace_ratio(html: str) -> float:
    text = re.sub(r"<[^>]+>", "", html)
    visible = len(" ".join(text.split()))
    total = max(len(html), 1)
    return round(max(0.0, min(1.0, 1.0 - (visible / total))), 3)


def extract_css_section_heights(css: str) -> list[str]:
    matches = re.findall(r"(?:min-height|height|max-height)\s*:\s*([^;]+)", css, flags=re.IGNORECASE)
    return [match.strip() for match in matches[:20]]


def coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else max(default, 1)
    except Exception:
        return max(default, 1)


def clamp_percent(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = float(default)
    return round(max(0.0, min(100.0, parsed)), 2)


def normalize_mapped_fields(raw_fields: Any, html: str) -> list[str]:
    fields: list[str] = []
    if isinstance(raw_fields, list):
        fields.extend(str(field).strip() for field in raw_fields if str(field).strip())
    fields.extend(extract_placeholders(html))
    return sorted(set(field for field in fields if field in ALLOWED_TEMPLATE_FIELDS))


def extract_placeholders(html: str) -> list[str]:
    return sorted(set(re.findall(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}", html)))


def sanitize_template_css(css: str) -> str:
    clean = css.strip()
    clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL)
    for pattern in DANGEROUS_CSS_PATTERNS:
        if re.search(pattern, clean, flags=re.IGNORECASE):
            raise ValueError(f"Generated CSS contains unsafe construct matching {pattern}")
    return clean


def enforce_readability_css(css: str) -> str:
    css = clamp_numeric_css_floor(css, "font-size", 11.0, {"px": 1.0, "pt": 1.333})
    css = clamp_line_height_floor(css, 1.35)
    css = clamp_numeric_css_floor(css, "padding", 12.0, {"px": 1.0, "pt": 1.333})
    css = clamp_numeric_css_floor(css, "padding-top", 12.0, {"px": 1.0, "pt": 1.333})
    css = clamp_numeric_css_floor(css, "padding-bottom", 12.0, {"px": 1.0, "pt": 1.333})
    css = clamp_numeric_css_floor(css, "padding-left", 12.0, {"px": 1.0, "pt": 1.333})
    css = clamp_numeric_css_floor(css, "padding-right", 12.0, {"px": 1.0, "pt": 1.333})
    return (
        css.rstrip()
        + "\n\n"
        + "html, body { line-height: 1.35; }\n"
        + "body, p, li, td, th { line-height: 1.35; }\n"
        + "h1, h2, h3, h4, h5, h6 { line-height: 1.35; }\n"
        + ".card, .panel, .section, .content-block, section, article { padding: 12px; overflow: visible; }\n"
        + ".skills, .skill-grid, .qualifications, .benefits, .cards, .grid, .metadata-grid, .requirements-grid { "
        + "display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); align-items: start; }\n"
        + "ul, ol { overflow: visible; }\n"
    )


def clamp_numeric_css_floor(css: str, property_name: str, floor_px: float, units: dict[str, float]) -> str:
    pattern = rf"({re.escape(property_name)}\s*:\s*)([0-9.]+)\s*(px|pt)([^;]*;)"

    def replace(match: re.Match[str]) -> str:
        prefix, value, unit, suffix = match.groups()
        parsed = float(value)
        multiplier = units.get(unit.lower(), 1.0)
        if parsed * multiplier >= floor_px:
            return match.group(0)
        clamped = floor_px / multiplier
        return f"{prefix}{round(clamped, 2)}{unit}{suffix}"

    return re.sub(pattern, replace, css, flags=re.IGNORECASE)


def clamp_line_height_floor(css: str, floor: float) -> str:
    pattern = r"(line-height\s*:\s*)([0-9.]+)(\s*;)"

    def replace(match: re.Match[str]) -> str:
        prefix, value, suffix = match.groups()
        parsed = float(value)
        if parsed >= floor:
            return match.group(0)
        return f"{prefix}{floor}{suffix}"

    return re.sub(pattern, replace, css, flags=re.IGNORECASE)


def sanitize_template_html(html: str) -> str:
    parser = SafeTemplateHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.html.strip()


class SafeTemplateHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.skip_stack: list[str] = []

    @property
    def html(self) -> str:
        return "".join(self.parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in DANGEROUS_HTML_TAGS:
            self.skip_stack.append(tag)
            return
        if self.skip_stack or tag not in ALLOWED_HTML_TAGS:
            return

        safe_attrs = []
        for name, value in attrs:
            name = name.lower()
            if name.startswith("on") or name not in ALLOWED_ATTRS:
                continue
            safe_value = str(value or "")
            if "javascript:" in safe_value.lower() or "http://" in safe_value.lower() or "https://" in safe_value.lower():
                continue
            safe_attrs.append(f'{name}="{escape(safe_value, quote=True)}"')
        attr_text = f" {' '.join(safe_attrs)}" if safe_attrs else ""
        self.parts.append(f"<{tag}{attr_text}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_stack:
            if tag == self.skip_stack[-1]:
                self.skip_stack.pop()
            return
        if tag in ALLOWED_HTML_TAGS and tag not in VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.skip_stack:
            return
        self.parts.append(escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        if not self.skip_stack:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self.skip_stack:
            self.parts.append(f"&#{name};")


def html_template_to_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True)
