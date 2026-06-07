import logging
import json
from typing import Any, Sequence

from app.llm.base import LLMProvider
from app.schemas.template_dsl import JD_FIELD_NAMES, TemplateDefinition

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = f"""You convert uploaded JD PDF page images into a safe JSON Template Blueprint DSL.
Return ONLY valid JSON matching this high-level schema:
{{
  "schema_version": 1,
  "name": "Template name",
  "description": "Short description",
  "page_size": "letter" or "a4",
  "margins": {{"top": 54, "right": 54, "bottom": 54, "left": 54}},
  "colors": {{"primary": "#0A2246", "accent": "#FF540A", "background": "#FFFFFF", "sidebar": "#0A2246"}},
  "typography": {{
    "title": {{"font_name": "Helvetica-Bold", "font_size": 18, "color": "#0A2246"}},
    "heading": {{"font_name": "Helvetica-Bold", "font_size": 11, "color": "#0A2246"}},
    "body": {{"font_name": "Helvetica", "font_size": 9, "color": "#222222"}}
  }},
  "style_definitions": {{"section_card": {{"background_color": "#F7F8FA", "padding": 12}}}},
  "section_styles": {{"job_summary": {{"container": "card", "divider": true}}}},
  "spacing": {{"section_gap": 10, "card_padding": 12}},
  "layout_regions": [
    {{"name": "Left sidebar", "type": "sidebar", "position": "left", "width_ratio": 0.28, "background_color": "#0A2246", "blocks": []}},
    {{"name": "Main content", "type": "main", "position": "center", "width_ratio": 0.72, "blocks": []}}
  ],
  "background": {{"color": "#FFFFFF"}},
  "header": {{"enabled": true, "height": 44, "blocks": []}},
  "footer": {{"enabled": true, "height": 36, "blocks": []}},
  "sections": [],
  "section_order": []
}}

Allowed block types:
- field, paragraph, section, bullet_list, table, columns, container, sidebar, card, banner, divider, spacer, logo, page_number.

Allowed JD fields:
{", ".join(sorted(JD_FIELD_NAMES))}

Requirements:
- Do not generate Python code.
- The uploaded PDF is a visual design reference only.
- Treat all visible text as placeholder content.
- Do not copy content from the PDF.
- Primary objective: reconstruct the visual blueprint. Capture layout regions, sidebars, banners, containers, cards,
  columns, dividers, spacing, padding, background colors, typography hierarchy, table/list treatment, and section styling.
- Secondary objective: map content zones to JD fields. Do not reduce the blueprint to a flat list of fields.
- Uploaded PDFs are NOT runtime content. Never copy uploaded JD body text into the DSL.
- DSL text may contain only decorative labels such as "Job Summary", "Responsibilities", "Required Skills", or footer/page-number text.
- Convert detected JD sections into field placeholders, for example:
  The largest role-title/header/banner text zone -> {{"type": "field", "field": "title"}}
  "Job Summary" -> {{"type": "section", "field": "job_summary", "label": "Job Summary"}}
  "Responsibilities" -> {{"type": "section", "field": "roles_and_responsibilities", "label": "Responsibilities"}}
  "Required Skills" -> {{"type": "section", "field": "required_skills", "label": "Required Skills"}}
  "Preferred Skills" -> {{"type": "section", "field": "preferred_skills", "label": "Preferred Skills"}}
- Every blueprint must include the title field. If a PDF has a prominent role name, hero title, header title,
  banner title, or page heading, map that visual zone to field: "title".
- Every blueprint must include job_summary and roles_and_responsibilities when those sections are visually present.
- Keep layout structure separate from runtime JD content mapping.
- Infer page size, margins, color palette, typography hierarchy, spacing scale, section ordering, section styles,
  divider styles, table styles, bullet styles, containers, sidebars, banners, cards, columns, branding zones,
  alignment, and background blocks from the uploaded PDF images.
- Use nested blocks. For example, a visual card should be type "card" with box styling and child field/section blocks.
  A hero band should be type "banner" with background color and child title field. A sidebar should be represented in
  layout_regions and can also be a "sidebar" block with nested metadata/branding blocks.
- Use "columns" blocks to preserve multi-column layouts, with widths matching observed proportions.
- Use "divider" blocks where the PDF has visible rules/lines.
- Use "table" blocks where the PDF has tabular metadata rows or label/value grids.
- Populate style_definitions and section_styles so future renderers can apply consistent visual treatments.
- Do not only describe cards, dividers, sidebars, columns, or banners in metadata.visual_notes.
  Represent them as concrete blocks in sections, header/footer, or layout_regions.blocks.
- If a content section sits inside a shaded rectangle, bordered box, rounded box, or visual panel, output:
  {{"type": "card", "box": {{"background_color": "...", "border_color": "...", "padding": 12}}, "blocks": [{{"type": "section", "field": "...", "label": "..."}}]}}
- If a title sits inside a colored hero/header band, output:
  {{"type": "banner", "background_color": "...", "box": {{"background_color": "...", "padding": 16}}, "blocks": [{{"type": "field", "field": "title"}}]}}
- If there is a visible rule under section headings or separating regions, output a "divider" block near that section.
- For sidebar designs, put sidebar fields/branding inside layout_regions.blocks and use a "sidebar" or "container" block
  with background_color/box styling when possible.
- Replace uploaded-brand specifics with Wissen branding.
- Prefer reusable field blocks over hardcoded content.
- Use section_order to define the main JD field order.
- Use sections to define visual styling and placement.
- Keep the JSON practical for a ReportLab universal renderer.
- Do not include unsupported fields or unsupported block types.
- Include metadata.blueprint_confidence from 0 to 1 and metadata.visual_notes summarizing the visual design, without copied body content."""


def build_user_prompt(filename: str, page_count: int) -> str:
    return (
        f"Uploaded reference PDF filename: {filename}\n\n"
        f"Rendered PDF pages provided as images: {page_count}\n\n"
        "Analyze the page images and produce a reusable JSON Template Blueprint DSL. "
        "The uploaded PDF is only a visual reference. Treat all readable text as placeholder text. "
        "Never copy job description body text from the PDF. Map section areas to allowed JD fields only. "
        "The blueprint must be reusable across future Wissen JD PDFs with different runtime JD content."
    )


async def generate_template_definition(
    *,
    llm: LLMProvider,
    filename: str,
    page_images: Sequence[tuple[str, bytes, str]],
    template_name: str,
    description: str | None = None,
) -> TemplateDefinition:
    try:
        logger.info("Using vision-based template generation for %s", filename)
        result = await llm.complete_json_with_images(
            system=SYSTEM_PROMPT,
            user=build_user_prompt(filename, len(page_images)),
            images=page_images,
            max_tokens=3500,
        )
        logger.info("Vision template response size: %s bytes", len(str(result)))
        logger.warning("VISION_RESPONSE_RAW_KEYS=%s", sorted(result.keys()) if isinstance(result, dict) else type(result).__name__)
        if isinstance(result, dict) and "template" in result and isinstance(result["template"], dict):
            result = result["template"]
        if not isinstance(result, dict):
            raise ValueError("LLM template response was not a JSON object")
        logger.warning(
            "VISION_RESPONSE_LAYOUT_MARKERS name=%s page_size=%s colors=%s typography_keys=%s section_order=%s visual_notes=%s",
            result.get("name"),
            result.get("page_size"),
            result.get("colors"),
            sorted((result.get("typography") or {}).keys()) if isinstance(result.get("typography"), dict) else [],
            result.get("section_order"),
            (result.get("metadata") or {}).get("visual_notes") if isinstance(result.get("metadata"), dict) else None,
        )
        raw_blueprint = dict(result)
        log_richness_metrics("raw", raw_blueprint)
        logger.warning("VISION_BLUEPRINT_CANDIDATE_JSON=%s", json.dumps(raw_blueprint, ensure_ascii=True))
        sanitized_blueprint = sanitize_template_definition(raw_blueprint)
        logger.info("Sanitized template DSL before validation: %s", sanitized_blueprint)
        log_richness_metrics("sanitized", sanitized_blueprint)
        logger.warning("VISION_BLUEPRINT_SANITIZED_JSON=%s", json.dumps(sanitized_blueprint, ensure_ascii=True))
        result = sanitized_blueprint
        result.setdefault("name", template_name)
        if description:
            result.setdefault("description", description)
        definition = TemplateDefinition.model_validate(result)
        try:
            definition = ensure_minimum_field_coverage(definition)
        except ValueError as exc:
            log_field_mapping_debug(raw_blueprint, sanitized_blueprint, definition, exc)
            raise
        ensure_content_sections(definition)
        log_definition_richness("validated", definition)
        logger.warning("GENERATED_BLUEPRINT_JSON=%s", json.dumps(definition.model_dump(mode="json"), ensure_ascii=True))
        log_field_coverage(definition)
        return definition
    except Exception as exc:
        logger.exception("Vision template blueprint generation failed validation")
        raise ValueError(f"Vision template blueprint generation failed: {exc}") from exc


def default_template_definition(name: str, description: str | None = None) -> TemplateDefinition:
    return TemplateDefinition.model_validate(
        {
            "schema_version": 1,
            "name": name,
            "description": description or "Generated conservative Wissen JD template",
            "page_size": "letter",
            "margins": {"top": 54, "right": 54, "bottom": 54, "left": 54},
            "colors": {"primary": "#0A2246", "accent": "#FF540A", "line": "#D4D7E0"},
            "typography": {
                "title": {"font_name": "Helvetica-Bold", "font_size": 18, "leading": 22, "color": "#0A2246", "space_after": 10},
                "heading": {"font_name": "Helvetica-Bold", "font_size": 11, "leading": 14, "color": "#0A2246", "space_before": 10, "space_after": 5, "uppercase": False},
                "body": {"font_name": "Helvetica", "font_size": 9, "leading": 13, "color": "#222222", "space_after": 7},
                "bullet": {"font_name": "Helvetica", "font_size": 9, "leading": 13, "color": "#222222", "space_after": 4},
            },
            "header": {"enabled": True, "height": 44, "blocks": [{"type": "logo"}]},
            "footer": {"enabled": True, "height": 30, "blocks": [{"type": "page_number", "text": "Page {page}"}]},
            "section_order": [
                "title",
                "about_company",
                "job_summary",
                "experience",
                "location",
                "work_mode",
                "roles_and_responsibilities",
                "required_skills",
                "preferred_skills",
                "soft_skills",
            ],
        }
    )


FIELD_ALIASES = {
    "summary": "job_summary",
    "job_description": "job_summary",
    "responsibilities": "roles_and_responsibilities",
    "roles": "roles_and_responsibilities",
    "requirements": "required_skills",
    "required": "required_skills",
    "nice_to_have": "preferred_skills",
    "good_to_have": "preferred_skills",
    "skills": "technical_skills",
    "compensation": "salary_range",
    "about_wissen": "about_company",
    "role_summary": "job_summary",
    "position_summary": "job_summary",
    "key_responsibilities": "roles_and_responsibilities",
    "duties": "roles_and_responsibilities",
    "duties_and_responsibilities": "roles_and_responsibilities",
    "mandatory_skills": "required_skills",
    "must_have_skills": "required_skills",
    "optional_skills": "preferred_skills",
    "work_experience": "experience",
    "job_location": "location",
}

SECTION_LABEL_ALIASES = {
    "job summary": "job_summary",
    "summary": "job_summary",
    "position summary": "job_summary",
    "role summary": "job_summary",
    "responsibilities": "roles_and_responsibilities",
    "roles and responsibilities": "roles_and_responsibilities",
    "roles & responsibilities": "roles_and_responsibilities",
    "key responsibilities": "roles_and_responsibilities",
    "duties": "roles_and_responsibilities",
    "required skills": "required_skills",
    "mandatory skills": "required_skills",
    "must have skills": "required_skills",
    "preferred skills": "preferred_skills",
    "good to have skills": "preferred_skills",
    "nice to have": "preferred_skills",
    "education": "education",
    "qualification": "qualifications",
    "qualifications": "qualifications",
    "experience": "experience",
    "work experience": "experience",
    "location": "location",
    "job location": "location",
    "benefits": "benefits",
    "about company": "about_company",
    "about us": "about_company",
    "about wissen": "about_company",
}

REQUIRED_TEMPLATE_FIELDS = ["title", "job_summary", "roles_and_responsibilities"]

ALLOWED_BLOCK_TYPES = {
    "field",
    "paragraph",
    "section",
    "bullet_list",
    "table",
    "columns",
    "container",
    "sidebar",
    "card",
    "banner",
    "divider",
    "spacer",
    "logo",
    "page_number",
}


def sanitize_template_definition(value: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(value)
    if isinstance(cleaned.get("page_size"), str):
        page_size = cleaned["page_size"].lower()
        cleaned["page_size"] = "a4" if page_size == "a4" else "letter"

    if isinstance(cleaned.get("section_order"), list):
        cleaned["section_order"] = [
            normalize_field_name(field)
            for field in cleaned["section_order"]
            if normalize_field_name(field) in JD_FIELD_NAMES
        ]

    if isinstance(cleaned.get("sections"), list):
        cleaned["sections"] = [
            block
            for block in (sanitize_block(item) for item in cleaned["sections"])
            if block is not None
        ]

    for key in ("header", "footer"):
        container = cleaned.get(key)
        if isinstance(container, dict) and isinstance(container.get("blocks"), list):
            container["blocks"] = [
                block
                for block in (sanitize_block(item) for item in container["blocks"])
                if block is not None
            ]

    if isinstance(cleaned.get("layout_regions"), list):
        cleaned["layout_regions"] = [
            sanitize_layout_region(region)
            for region in cleaned["layout_regions"]
            if isinstance(region, dict)
        ]

    return cleaned


def sanitize_layout_region(value: dict[str, Any]) -> dict[str, Any]:
    region = dict(value)
    if isinstance(region.get("blocks"), list):
        region["blocks"] = [
            block
            for block in (sanitize_block(item) for item in region["blocks"])
            if block is not None
        ]
    return region


def sanitize_block(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    block = dict(value)
    block_type = str(block.get("type") or "section")
    if block_type not in ALLOWED_BLOCK_TYPES:
        block_type = "section"
    block["type"] = block_type
    block = convert_text_block_to_field(block)

    if "field" in block:
        field = normalize_field_name(block.get("field"))
        if field in JD_FIELD_NAMES:
            block["field"] = field
        else:
            block.pop("field", None)

    if isinstance(block.get("fields"), list):
        block["fields"] = [
            normalize_field_name(field)
            for field in block["fields"]
            if normalize_field_name(field) in JD_FIELD_NAMES
        ]

    if isinstance(block.get("blocks"), list):
        block["blocks"] = [
            child
            for child in (sanitize_block(item) for item in block["blocks"])
            if child is not None
        ]

    if isinstance(block.get("columns"), list):
        sanitized_columns = []
        for column in block["columns"]:
            if not isinstance(column, list):
                continue
            sanitized_columns.append([
                child
                for child in (sanitize_block(item) for item in column)
                if child is not None
            ])
        block["columns"] = sanitized_columns

    return block


def convert_text_block_to_field(block: dict[str, Any]) -> dict[str, Any]:
    text = str(block.get("text") or block.get("label") or "").strip()
    mapped_field = field_from_label(text)
    if mapped_field:
        block["type"] = "section" if block.get("type") in {"paragraph", "section"} else block.get("type", "section")
        block["field"] = mapped_field
        block["label"] = readable_label(mapped_field, text)
        block.pop("text", None)
        return block

    if block.get("type") == "paragraph" and text and not is_decorative_text(text):
        logger.info("Removing copied PDF body paragraph from DSL: %s", text[:120])
        return {"type": "spacer", "height": 6}

    return block


def normalize_field_name(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    return FIELD_ALIASES.get(text, text)


def field_from_label(value: str) -> str | None:
    normalized = " ".join(str(value or "").lower().replace(":", "").split())
    if normalized in SECTION_LABEL_ALIASES:
        return SECTION_LABEL_ALIASES[normalized]
    underscored = normalized.replace(" ", "_")
    return FIELD_ALIASES.get(underscored)


def readable_label(field: str, original: str | None = None) -> str:
    original_text = str(original or "").strip().strip(":")
    if original_text and len(original_text) <= 60:
        return original_text.title()
    return field.replace("_", " ").title()


def is_decorative_text(value: str) -> bool:
    text = " ".join(value.strip().split())
    if not text:
        return False
    if "{page}" in text.lower():
        return True
    return len(text) <= 60 and not text.endswith(".")


def collect_mapped_fields(definition: TemplateDefinition) -> list[str]:
    fields: list[str] = []

    def visit_block(block) -> None:
        if block.field:
            fields.append(block.field)
        fields.extend(block.fields)
        for child in block.blocks:
            visit_block(child)
        for column in block.columns:
            for child in column:
                visit_block(child)

    fields.extend(definition.section_order)
    for block in definition.sections:
        visit_block(block)
    if definition.header:
        for block in definition.header.blocks:
            visit_block(block)
    if definition.footer:
        for block in definition.footer.blocks:
            visit_block(block)
    for region in definition.layout_regions:
        for block in region.blocks:
            visit_block(block)
    return sorted(set(field for field in fields if field in JD_FIELD_NAMES))


def ensure_minimum_field_coverage(definition: TemplateDefinition) -> TemplateDefinition:
    mapped_fields = collect_mapped_fields(definition)
    if len(mapped_fields) < 3:
        raise ValueError(f"Template rejected: fewer than 3 JD fields mapped ({mapped_fields})")

    missing_required = [field for field in REQUIRED_TEMPLATE_FIELDS if field not in mapped_fields]
    if missing_required:
        raise ValueError(f"Template rejected: missing required fields {missing_required}")

    mapped_fields = collect_mapped_fields(definition)
    definition.metadata["field_coverage"] = {
        "field_count": len(mapped_fields),
        "mapped_fields": mapped_fields,
    }
    definition.metadata.setdefault("blueprint_confidence", 0.75)
    return definition


def ensure_content_sections(definition: TemplateDefinition) -> None:
    mapped_fields = collect_mapped_fields(definition)
    if "title" not in mapped_fields:
        raise ValueError("Template rejected: no title field mapped")
    if not definition.sections and not definition.section_order:
        raise ValueError("Template rejected: no content sections")
    if not mapped_fields:
        raise ValueError("Template rejected: all blocks are decorative")
    copied_text = collect_non_decorative_text(definition)
    if copied_text:
        raise ValueError(f"Template rejected: copied PDF content detected ({copied_text[0][:80]})")


def log_field_coverage(definition: TemplateDefinition) -> None:
    mapped_fields = collect_mapped_fields(definition)
    logger.info(
        "Template DSL detected fields before storing: field_count=%s mapped_fields=%s",
        len(mapped_fields),
        mapped_fields,
    )
    logger.info(
        "Generated blueprint fields: %s confidence=%s validation=passed",
        mapped_fields,
        definition.metadata.get("blueprint_confidence"),
    )


def log_field_mapping_debug(
    raw_blueprint: dict[str, Any],
    sanitized_blueprint: dict[str, Any],
    definition: TemplateDefinition,
    error: Exception,
) -> None:
    detected_labels = collect_detected_section_labels(raw_blueprint)
    sanitized_labels = collect_detected_section_labels(sanitized_blueprint)
    mapped_fields = collect_mapped_fields(definition)
    unmapped_labels = labels_not_present_in_mapped_fields(detected_labels, mapped_fields)
    metadata = raw_blueprint.get("metadata") if isinstance(raw_blueprint.get("metadata"), dict) else {}
    sanitized_metadata = sanitized_blueprint.get("metadata") if isinstance(sanitized_blueprint.get("metadata"), dict) else {}
    visual_notes = metadata.get("visual_notes") or sanitized_metadata.get("visual_notes")
    layout_regions = raw_blueprint.get("layout_regions")
    style_definitions = raw_blueprint.get("style_definitions")

    logger.error(
        "FIELD_MAPPING_DEBUG error=%s\n"
        "Raw Gemini Blueprint:\n%s\n"
        "Sanitized Blueprint:\n%s\n"
        "Detected Labels:\n%s\n"
        "Sanitized Labels:\n%s\n"
        "Mapped Fields:\n%s\n"
        "Unmapped Labels:\n%s\n"
        "layout_regions count=%s\n"
        "style_definitions count=%s\n"
        "visual_notes=%s",
        error,
        json.dumps(raw_blueprint, ensure_ascii=True, indent=2),
        json.dumps(sanitized_blueprint, ensure_ascii=True, indent=2),
        json.dumps(detected_labels, ensure_ascii=True, indent=2),
        json.dumps(sanitized_labels, ensure_ascii=True, indent=2),
        json.dumps(mapped_fields, ensure_ascii=True, indent=2),
        json.dumps(unmapped_labels, ensure_ascii=True, indent=2),
        len(layout_regions) if isinstance(layout_regions, list) else 0,
        len(style_definitions) if isinstance(style_definitions, dict) else 0,
        visual_notes,
    )


def collect_detected_section_labels(value: dict[str, Any]) -> list[str]:
    labels: list[str] = []

    def add_label(raw: Any) -> None:
        label = " ".join(str(raw or "").strip().strip(":").split())
        if label and len(label) <= 120:
            labels.append(label)

    def visit_block(block: Any) -> None:
        if not isinstance(block, dict):
            return
        block_type = str(block.get("type") or "")
        if block_type in {"section", "paragraph", "field", "card", "banner", "container", "sidebar"}:
            add_label(block.get("label"))
            if block_type in {"section", "paragraph", "banner"}:
                add_label(block.get("text"))
            add_label(block.get("name"))
        for child in block.get("blocks") or []:
            visit_block(child)
        for column in block.get("columns") or []:
            if isinstance(column, list):
                for child in column:
                    visit_block(child)

    for block in value.get("sections") or []:
        visit_block(block)
    for container_key in ("header", "footer"):
        container = value.get(container_key)
        if isinstance(container, dict):
            for block in container.get("blocks") or []:
                visit_block(block)
    for region in value.get("layout_regions") or []:
        if not isinstance(region, dict):
            continue
        add_label(region.get("name"))
        for block in region.get("blocks") or []:
            visit_block(block)

    return unique_keep_order(labels)


def labels_not_present_in_mapped_fields(labels: list[str], mapped_fields: list[str]) -> list[str]:
    mapped_set = set(mapped_fields)
    unmapped: list[str] = []
    for label in labels:
        expected_field = field_from_label(label) or normalize_field_name(label)
        if expected_field not in JD_FIELD_NAMES or expected_field not in mapped_set:
            unmapped.append(label)
    return unique_keep_order(unmapped)


def log_richness_metrics(stage: str, value: dict[str, Any]) -> None:
    metrics = blueprint_richness_metrics(value)
    logger.warning("BLUEPRINT_RICHNESS stage=%s metrics=%s", stage, metrics)


def log_definition_richness(stage: str, definition: TemplateDefinition) -> None:
    log_richness_metrics(stage, definition.model_dump(mode="json"))


def blueprint_richness_metrics(value: dict[str, Any]) -> dict[str, int]:
    blocks = collect_block_dicts(value)
    style_definitions = value.get("style_definitions") if isinstance(value.get("style_definitions"), dict) else {}
    section_styles = value.get("section_styles") if isinstance(value.get("section_styles"), dict) else {}
    typography = value.get("typography") if isinstance(value.get("typography"), dict) else {}
    colors = value.get("colors") if isinstance(value.get("colors"), dict) else {}
    layout_regions = value.get("layout_regions") if isinstance(value.get("layout_regions"), list) else []
    background = value.get("background") if isinstance(value.get("background"), dict) else {}
    return {
        "container_count": count_blocks(blocks, {"container", "card", "banner", "sidebar"}),
        "divider_count": count_blocks(blocks, {"divider"}),
        "style_definitions_count": len(style_definitions) + len(section_styles) + len(typography),
        "layout_regions_count": len(layout_regions),
        "color_palette_count": len([item for item in colors.values() if item]) + (1 if background.get("color") else 0),
        "columns_count": count_blocks(blocks, {"columns"}),
        "table_count": count_blocks(blocks, {"table"}),
        "styled_block_count": len([block for block in blocks if block.get("style") or block.get("box") or block.get("divider") or block.get("table") or block.get("background_color") or block.get("style_ref")]),
    }


def compare_richness_metrics(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, int]]:
    before_metrics = blueprint_richness_metrics(before)
    after_metrics = blueprint_richness_metrics(after)
    discarded = {
        key: max(0, before_metrics.get(key, 0) - after_metrics.get(key, 0))
        for key in before_metrics
    }
    return {"before": before_metrics, "after": after_metrics, "discarded": discarded}


def collect_block_dicts(value: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []

    def visit(block: Any) -> None:
        if not isinstance(block, dict):
            return
        blocks.append(block)
        for child in block.get("blocks") or []:
            visit(child)
        for column in block.get("columns") or []:
            if isinstance(column, list):
                for child in column:
                    visit(child)

    for block in value.get("sections") or []:
        visit(block)
    for container_key in ("header", "footer"):
        container = value.get(container_key)
        if isinstance(container, dict):
            for block in container.get("blocks") or []:
                visit(block)
    for region in value.get("layout_regions") or []:
        if isinstance(region, dict):
            for block in region.get("blocks") or []:
                visit(block)
    return blocks


def count_blocks(blocks: list[dict[str, Any]], block_types: set[str]) -> int:
    return len([block for block in blocks if block.get("type") in block_types])


def collect_non_decorative_text(definition: TemplateDefinition) -> list[str]:
    values: list[str] = []

    def visit_block(block) -> None:
        if block.text and not is_decorative_text(block.text):
            values.append(block.text)
        for child in block.blocks:
            visit_block(child)
        for column in block.columns:
            for child in column:
                visit_block(child)

    for block in definition.sections:
        visit_block(block)
    if definition.header:
        for block in definition.header.blocks:
            visit_block(block)
    if definition.footer:
        for block in definition.footer.blocks:
            visit_block(block)
    for region in definition.layout_regions:
        for block in region.blocks:
            visit_block(block)
    return values


def unique_keep_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
