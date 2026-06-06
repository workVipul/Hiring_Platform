import logging
from typing import Any

from app.llm.base import LLMProvider
from app.schemas.template_dsl import JD_FIELD_NAMES, TemplateDefinition

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = f"""You convert uploaded JD PDF references into a safe JSON template definition DSL.
Return ONLY valid JSON matching this high-level schema:
{{
  "schema_version": 1,
  "name": "Template name",
  "description": "Short description",
  "page_size": "letter" or "a4",
  "margins": {{"top": 54, "right": 54, "bottom": 54, "left": 54}},
  "colors": {{"primary": "#0A2246", "accent": "#FF540A"}},
  "typography": {{"title": {{"font_name": "Helvetica-Bold", "font_size": 18, "color": "#0A2246"}}}},
  "header": {{"enabled": true, "height": 44, "blocks": []}},
  "footer": {{"enabled": true, "height": 36, "blocks": []}},
  "sections": [],
  "section_order": []
}}

Allowed block types:
- field, paragraph, section, bullet_list, table, columns, card, banner, divider, spacer, logo, page_number.

Allowed JD fields:
{", ".join(sorted(JD_FIELD_NAMES))}

Requirements:
- Do not generate Python code.
- Uploaded PDFs are visual references only. Never copy uploaded JD body text into the DSL.
- DSL text may contain only decorative labels such as "Job Summary", "Responsibilities", "Required Skills", or footer/page-number text.
- Convert detected JD sections into field placeholders, for example:
  "Job Summary" -> {{"type": "section", "field": "job_summary", "label": "Job Summary"}}
  "Responsibilities" -> {{"type": "section", "field": "roles_and_responsibilities", "label": "Responsibilities"}}
  "Required Skills" -> {{"type": "section", "field": "required_skills", "label": "Required Skills"}}
  "Preferred Skills" -> {{"type": "section", "field": "preferred_skills", "label": "Preferred Skills"}}
- Keep layout structure separate from runtime JD content mapping.
- Infer page size, margins, colors, typography, spacing, section ordering, section styles, divider styles, table styles, bullet styles, containers, branding zones, and alignment from the uploaded PDF context.
- Replace uploaded-brand specifics with Wissen branding.
- Prefer reusable field blocks over hardcoded content.
- Use section_order to define the main JD field order.
- Use sections to define visual styling and placement.
- Keep the JSON practical for a ReportLab universal renderer.
- Do not include unsupported fields or unsupported block types."""


def build_user_prompt(filename: str, extracted_context: str) -> str:
    return (
        f"Uploaded reference PDF filename: {filename}\n\n"
        "Analyze this PDF context and produce a reusable JSON DSL template definition. "
        "The DSL must mimic the uploaded PDF style for future Wissen JD PDFs.\n\n"
        f"{extracted_context[:9000] if extracted_context.strip() else 'No extractable text was available. Produce a clean, conservative Wissen-branded template definition.'}"
    )


async def generate_template_definition(
    *,
    llm: LLMProvider,
    filename: str,
    extracted_context: str,
    template_name: str,
    description: str | None = None,
) -> TemplateDefinition:
    try:
        result = await llm.complete_json(
            system=SYSTEM_PROMPT,
            user=build_user_prompt(filename, extracted_context),
            max_tokens=3500,
        )
        if isinstance(result, dict) and "template" in result and isinstance(result["template"], dict):
            result = result["template"]
        if not isinstance(result, dict):
            raise ValueError("LLM template response was not a JSON object")
        result = sanitize_template_definition(result)
        logger.info("Sanitized template DSL before validation: %s", result)
        result.setdefault("name", template_name)
        if description:
            result.setdefault("description", description)
        definition = TemplateDefinition.model_validate(result)
        definition = ensure_minimum_field_coverage(definition)
        if not definition.sections and not definition.section_order:
            definition = default_template_definition(template_name, description)
        log_field_coverage(definition)
        return definition
    except Exception as exc:
        logger.warning("Template DSL generation failed; using safe fallback DSL: %s", exc)
        fallback = default_template_definition(template_name, description)
        fallback.metadata["generation_warning"] = str(exc)[:500]
        logger.info("Fallback template DSL section_order=%s", fallback.section_order)
        log_field_coverage(fallback)
        return fallback


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

    return cleaned


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
    return sorted(set(field for field in fields if field in JD_FIELD_NAMES))


def ensure_minimum_field_coverage(definition: TemplateDefinition) -> TemplateDefinition:
    mapped_fields = collect_mapped_fields(definition)
    if len(mapped_fields) < 3:
        raise ValueError(f"Template rejected: fewer than 3 JD fields mapped ({mapped_fields})")

    missing_required = [field for field in REQUIRED_TEMPLATE_FIELDS if field not in mapped_fields]
    if missing_required:
        logger.warning("Template DSL missing required fields %s; injecting required field sections", missing_required)
        definition.section_order = unique_keep_order([*definition.section_order, *missing_required])

    mapped_fields = collect_mapped_fields(definition)
    definition.metadata["field_coverage"] = {
        "field_count": len(mapped_fields),
        "mapped_fields": mapped_fields,
    }
    return definition


def log_field_coverage(definition: TemplateDefinition) -> None:
    mapped_fields = collect_mapped_fields(definition)
    logger.info(
        "Template DSL detected fields before storing: field_count=%s mapped_fields=%s",
        len(mapped_fields),
        mapped_fields,
    )


def unique_keep_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
