import json
import logging
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.template_dsl import TemplateBlock, TemplateDefinition
from app.services.pdf_common import (
    ABOUT_WISSEN,
    WISSEN_SITES,
    as_list,
    build_wissen_logo_table,
    format_experience,
)


ALIGNMENTS = {"LEFT": TA_LEFT, "CENTER": TA_CENTER, "RIGHT": TA_RIGHT, "JUSTIFY": TA_JUSTIFY}
PAGE_SIZES = {"letter": letter, "a4": A4}
logger = logging.getLogger(__name__)


class RenderDiagnostics:
    def __init__(self) -> None:
        self.section_count = 0
        self.rendered_section_count = 0
        self.skipped_section_count = 0
        self.skipped_reasons: list[str] = []

    def log_field(self, field: str, value: Any, path: str) -> None:
        logger.info(
            "Dynamic template field path=%s field=%s resolved_key=%s content_length=%s",
            path,
            field or "<none>",
            field or "<none>",
            content_length(value),
        )

    def rendered(self, path: str, block_type: str, count: bool = True) -> None:
        if count:
            self.rendered_section_count += 1
        logger.info("Dynamic template rendered block path=%s type=%s", path, block_type)

    def skipped(self, path: str, block_type: str, reason: str, count: bool = True) -> None:
        message = f"{path} ({block_type}): {reason}"
        if count:
            self.skipped_section_count += 1
            self.skipped_reasons.append(message)
        logger.warning("Dynamic template skipped block %s", message)


def render_dynamic_template(output_path: Path, title: str, data: dict, metadata: dict, definition_json: dict) -> None:
    definition = TemplateDefinition.model_validate(definition_json)
    logger.info(
        "Dynamic template final DSL for %s: %s",
        output_path,
        json.dumps(definition.model_dump(mode="json"), ensure_ascii=True)[:12000],
    )
    page_size = PAGE_SIZES.get(definition.page_size, letter)
    margins = definition.margins
    printable_width = page_size[0] - margins["left"] - margins["right"]

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        rightMargin=margins["right"],
        leftMargin=margins["left"],
        topMargin=margins["top"],
        bottomMargin=margins["bottom"],
    )
    field_data = build_field_data(title, data, metadata)
    logger.info(
        "Dynamic template field data lengths: %s",
        {field: content_length(value) for field, value in field_data.items()},
    )
    styles = build_styles(definition)
    story: list[Any] = []
    diagnostics = RenderDiagnostics()

    if definition.header and definition.header.enabled:
        story.extend(render_blocks(definition.header.blocks, field_data, styles, printable_width, diagnostics, "header", count_sections=False))

    blocks = merge_definition_blocks(definition)
    diagnostics.section_count = len(blocks)
    story.extend(render_blocks(blocks, field_data, styles, printable_width, diagnostics, "body", count_sections=True))

    if not blocks:
        fallback_blocks = default_content_blocks()
        diagnostics.section_count = len(fallback_blocks)
        diagnostics.skipped("body", "template", "DSL had no sections and no section_order; using default content blocks")
        story.extend(render_blocks(fallback_blocks, field_data, styles, printable_width, diagnostics, "body.default", count_sections=True))

    if diagnostics.rendered_section_count == 0:
        logger.error(
            "Dynamic template rendered zero content sections. section_count=%s skipped=%s reasons=%s",
            diagnostics.section_count,
            diagnostics.skipped_section_count,
            diagnostics.skipped_reasons,
        )
        story.append(debug_paragraph(diagnostics, styles))
        story.extend(render_blocks(default_content_blocks(), field_data, styles, printable_width, diagnostics, "body.emergency_default", count_sections=True))

    logger.info(
        "Dynamic template render diagnostics: section_count=%s rendered_section_count=%s skipped_section_count=%s",
        diagnostics.section_count,
        diagnostics.rendered_section_count,
        diagnostics.skipped_section_count,
    )

    doc.build(
        story,
        onFirstPage=lambda canvas, doc_obj: draw_footer(canvas, doc_obj, definition, field_data, styles),
        onLaterPages=lambda canvas, doc_obj: draw_footer(canvas, doc_obj, definition, field_data, styles),
    )


def build_field_data(title: str, data: dict, metadata: dict) -> dict[str, Any]:
    required = as_list(data.get("requirements"))
    if not required:
        required = [f"Strong expertise in {skill}" for skill in as_list(data.get("skills"))]
    return {
        "title": title,
        "job_summary": data.get("summary") or data.get("job_summary") or data.get("content"),
        "about_company": data.get("about_company") or ABOUT_WISSEN,
        "roles_and_responsibilities": data.get("responsibilities") or data.get("roles_and_responsibilities"),
        "required_skills": required,
        "preferred_skills": data.get("nice_to_have") or data.get("preferred_skills") or data.get("good_to_have"),
        "technical_skills": data.get("skills") or metadata.get("must_have_skills"),
        "soft_skills": data.get("soft_skills") or data.get("resume_skills"),
        "qualifications": data.get("qualifications") or required,
        "education": metadata.get("education") or data.get("education"),
        "experience": format_experience(metadata.get("experience_years") or metadata.get("experience") or data.get("experience")),
        "location": metadata.get("location") or data.get("location"),
        "employment_type": metadata.get("employment_type") or data.get("employment_type"),
        "notice_period": metadata.get("notice_period") or data.get("notice_period"),
        "salary_range": data.get("compensation") or metadata.get("salary_range") or data.get("salary_range"),
        "benefits": data.get("benefits") or metadata.get("benefits"),
        "project_details": metadata.get("project_details") or metadata.get("industry_or_domain"),
        "team_details": metadata.get("team_details"),
        "industry": metadata.get("industry") or metadata.get("industry_or_domain"),
        "department": metadata.get("department"),
        "reporting_manager": metadata.get("reporting_manager"),
        "travel_requirements": metadata.get("travel_requirements"),
        "work_mode": metadata.get("work_mode") or data.get("work_mode"),
        "certifications": metadata.get("certifications"),
        "languages": metadata.get("languages"),
        "selection_process": metadata.get("selection_process"),
        "additional_information": data.get("additional_information") or metadata.get("additional_information"),
        "contact_information": metadata.get("contact_information"),
        "metadata": metadata,
    }


def build_styles(definition: TemplateDefinition) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    typography = definition.typography
    return {
        "title": style_from_dsl("DynamicTitle", typography.get("title"), sample["Normal"], font_name="Helvetica-Bold", font_size=18, color="#0A2246"),
        "heading": style_from_dsl("DynamicHeading", typography.get("heading"), sample["Normal"], font_name="Helvetica-Bold", font_size=11, color="#0A2246"),
        "body": style_from_dsl("DynamicBody", typography.get("body"), sample["Normal"], font_name="Helvetica", font_size=9, color="#222222"),
        "bullet": style_from_dsl("DynamicBullet", typography.get("bullet"), sample["Normal"], font_name="Helvetica", font_size=9, color="#222222", left_indent=14, first_line_indent=-9),
        "small": style_from_dsl("DynamicSmall", typography.get("small"), sample["Normal"], font_name="Helvetica", font_size=8, color="#445377"),
    }


def style_from_dsl(name: str, dsl_style: Any, parent: ParagraphStyle, **defaults) -> ParagraphStyle:
    font_name = getattr(dsl_style, "font_name", defaults.get("font_name", "Helvetica"))
    font_size = getattr(dsl_style, "font_size", defaults.get("font_size", 9))
    leading = getattr(dsl_style, "leading", None) or font_size + 3
    alignment = ALIGNMENTS.get(getattr(dsl_style, "alignment", "LEFT"), TA_LEFT)
    text_color = parse_color(getattr(dsl_style, "color", defaults.get("color", "#222222")))
    return ParagraphStyle(
        name,
        parent=parent,
        fontName=font_name,
        fontSize=font_size,
        leading=leading,
        textColor=text_color,
        alignment=alignment,
        spaceBefore=getattr(dsl_style, "space_before", 0),
        spaceAfter=getattr(dsl_style, "space_after", 6),
        leftIndent=defaults.get("left_indent", 0),
        firstLineIndent=defaults.get("first_line_indent", 0),
    )


def blocks_from_section_order(section_order: list[str]) -> list[TemplateBlock]:
    return [TemplateBlock(type="section", field=field, label=field.replace("_", " ").title()) for field in section_order]


def merge_definition_blocks(definition: TemplateDefinition) -> list[TemplateBlock]:
    blocks = list(definition.sections)
    existing_fields = fields_in_blocks(blocks)
    for field in definition.section_order:
        if field not in existing_fields:
            blocks.append(TemplateBlock(type="section", field=field, label=field.replace("_", " ").title()))
    return blocks


def fields_in_blocks(blocks: list[TemplateBlock]) -> set[str]:
    fields: set[str] = set()

    def visit(block: TemplateBlock) -> None:
        if block.field:
            fields.add(block.field)
        fields.update(block.fields)
        for child in block.blocks:
            visit(child)
        for column in block.columns:
            for child in column:
                visit(child)

    for block in blocks:
        visit(block)
    return fields


def default_content_blocks() -> list[TemplateBlock]:
    return blocks_from_section_order(["title", "job_summary", "roles_and_responsibilities", "required_skills", "preferred_skills", "about_company"])


def render_blocks(
    blocks: list[TemplateBlock],
    field_data: dict[str, Any],
    styles: dict[str, ParagraphStyle],
    width: float,
    diagnostics: RenderDiagnostics,
    path: str,
    count_sections: bool = True,
) -> list[Any]:
    story: list[Any] = []
    for index, block in enumerate(blocks):
        story.extend(render_block(block, field_data, styles, width, diagnostics, f"{path}.{index}", count_sections=count_sections))
    return story


def render_block(
    block: TemplateBlock,
    field_data: dict[str, Any],
    styles: dict[str, ParagraphStyle],
    width: float,
    diagnostics: RenderDiagnostics,
    path: str,
    count_sections: bool = True,
) -> list[Any]:
    if block.type == "spacer":
        return [Spacer(1, block.height)]
    if block.type == "divider":
        return [Spacer(1, (block.divider.space_before if block.divider else 6)), line_table(width, block), Spacer(1, (block.divider.space_after if block.divider else 6))]
    if block.type == "logo":
        logo = build_wissen_logo_table(width, align="LEFT")
        return [logo] if logo else []
    if block.type == "paragraph":
        if not block.text:
            diagnostics.skipped(path, block.type, "paragraph text is empty", count_sections)
            return []
        diagnostics.rendered(path, block.type, count_sections)
        return [Paragraph(str(block.text), block_style(block, styles["body"]))]
    if block.type == "field":
        value = field_data.get(block.field or "")
        diagnostics.log_field(block.field or "", value, path)
        rendered = render_value(block.field or "", block.label, value, block_style(block, styles["body"]), styles["bullet"])
        if rendered:
            diagnostics.rendered(path, block.type, count_sections)
        else:
            diagnostics.skipped(path, block.type, f"field {block.field or '<none>'} resolved empty", count_sections)
        return rendered
    if block.type == "section":
        value = field_data.get(block.field or "")
        diagnostics.log_field(block.field or "", value, path)
        if not value:
            diagnostics.skipped(path, block.type, f"field {block.field or '<none>'} resolved empty", count_sections)
            return []
        label = block.label or (block.field or "").replace("_", " ").title()
        diagnostics.rendered(path, block.type, count_sections)
        return [Paragraph(label.upper() if should_uppercase(block, styles["heading"]) else label, styles["heading"]), *render_value(block.field or "", None, value, styles["body"], styles["bullet"])]
    if block.type in {"card", "banner", "container", "sidebar"}:
        inner = render_blocks(block.blocks or [TemplateBlock(type="field", field=block.field, label=block.label)], field_data, styles, width, diagnostics, f"{path}.inner", count_sections=False)
        if not inner:
            diagnostics.skipped(path, block.type, "container inner blocks rendered empty", count_sections)
            return []
        diagnostics.rendered(path, block.type, count_sections)
        return wrap_in_table(inner, width, block)
    if block.type == "bullet_list":
        values = []
        for field in block.fields or ([block.field] if block.field else []):
            value = field_data.get(field)
            diagnostics.log_field(field or "", value, path)
            values.extend([item for item in as_list(value) if item])
        rendered = [Paragraph(f"&bull; {item}", block_style(block, styles["bullet"])) for item in values]
        if rendered:
            diagnostics.rendered(path, block.type, count_sections)
        else:
            diagnostics.skipped(path, block.type, "bullet list fields resolved empty", count_sections)
        return rendered
    if block.type == "table":
        rendered = render_table(block, field_data, styles, width, diagnostics, path)
        if rendered:
            diagnostics.rendered(path, block.type, count_sections)
        else:
            diagnostics.skipped(path, block.type, "table fields resolved empty", count_sections)
        return rendered
    if block.type == "columns":
        rendered = render_columns(block, field_data, styles, width, diagnostics, path)
        if rendered:
            diagnostics.rendered(path, block.type, count_sections)
        else:
            diagnostics.skipped(path, block.type, "columns rendered empty", count_sections)
        return rendered
    return []


def render_value(field: str, label: str | None, value: Any, body_style: ParagraphStyle, bullet_style: ParagraphStyle) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return [Paragraph(f"&bull; {item}", bullet_style) for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [Paragraph(f"<b>{key.replace('_', ' ').title()}</b>: {val}", body_style) for key, val in value.items() if val]
    prefix = f"<b>{label}</b>: " if label else ""
    return [Paragraph(f"{prefix}{value}", body_style)]


def render_table(block: TemplateBlock, field_data: dict[str, Any], styles: dict[str, ParagraphStyle], width: float, diagnostics: RenderDiagnostics, path: str) -> list[Any]:
    rows = []
    for field in block.fields:
        value = field_data.get(field)
        diagnostics.log_field(field, value, path)
        if value:
            rows.append([Paragraph(field.replace("_", " ").title(), styles["heading"]), Paragraph(", ".join(map(str, as_list(value))) if isinstance(value, list) else str(value), styles["body"])])
    if not rows:
        return []
    table = Table(rows, colWidths=[width * 0.32, width * 0.68])
    style = block.table
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, parse_color(style.border_color if style else "#D4D7E0")),
        ("BACKGROUND", (0, 0), (0, -1), parse_color(style.header_background if style and style.header_background else "#E8ECF2")),
        ("LEFTPADDING", (0, 0), (-1, -1), style.cell_padding if style else 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), style.cell_padding if style else 6),
        ("TOPPADDING", (0, 0), (-1, -1), style.cell_padding if style else 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), style.cell_padding if style else 6),
    ]))
    return [table, Spacer(1, 8)]


def render_columns(block: TemplateBlock, field_data: dict[str, Any], styles: dict[str, ParagraphStyle], width: float, diagnostics: RenderDiagnostics, path: str) -> list[Any]:
    columns = block.columns or []
    if not columns:
        return []
    col_widths = block.widths if len(block.widths) == len(columns) else [1 / len(columns)] * len(columns)
    normalized_widths = [width * item / sum(col_widths) for item in col_widths]
    cells = [render_blocks(column, field_data, styles, normalized_widths[index], diagnostics, f"{path}.column{index}", count_sections=False) for index, column in enumerate(columns)]
    if not any(cell for cell in cells):
        return []
    table = Table([cells], colWidths=normalized_widths)
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return [table, Spacer(1, 8)]


def wrap_in_table(flowables: list[Any], width: float, block: TemplateBlock) -> list[Any]:
    box = block.box
    table = Table([[flowables]], colWidths=[width])
    default_padding = box.padding if box else 10
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), parse_color(block.background_color or (box.background_color if box and box.background_color else "#F7F8FA"))),
        ("BOX", (0, 0), (-1, -1), box.border_width if box else 0, parse_color(box.border_color if box and box.border_color else "#D4D7E0")),
        ("LEFTPADDING", (0, 0), (-1, -1), box.padding_left if box and box.padding_left is not None else default_padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), box.padding_right if box and box.padding_right is not None else default_padding),
        ("TOPPADDING", (0, 0), (-1, -1), box.padding_top if box and box.padding_top is not None else default_padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), box.padding_bottom if box and box.padding_bottom is not None else default_padding),
    ]))
    return [table, Spacer(1, 8)]


def line_table(width: float, block: TemplateBlock) -> Table:
    divider = block.divider
    table = Table([[""]], colWidths=[width], rowHeights=[1])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), divider.width if divider else 0.8, parse_color(divider.color if divider else "#D4D7E0"))]))
    return table


def block_style(block: TemplateBlock, fallback: ParagraphStyle) -> ParagraphStyle:
    if not block.style:
        return fallback
    return style_from_dsl(f"{fallback.name}_{id(block)}", block.style, fallback)


def should_uppercase(block: TemplateBlock, style: ParagraphStyle) -> bool:
    return bool(block.style and block.style.uppercase)


def draw_footer(canvas, doc, definition: TemplateDefinition, field_data: dict[str, Any], styles: dict[str, ParagraphStyle]) -> None:
    if not definition.footer or not definition.footer.enabled:
        return
    canvas.saveState()
    footer_text = f"Page {doc.page}"
    for block in definition.footer.blocks:
        if block.type == "page_number":
            footer_text = (block.text or "Page {page}").replace("{page}", str(doc.page))
            break
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(parse_color("#445377"))
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, max(18, doc.bottomMargin / 2), footer_text)
    canvas.restoreState()


def parse_color(value: str | None):
    if not value:
        return colors.HexColor("#222222")
    try:
        return colors.HexColor(value)
    except Exception:
        return colors.HexColor("#222222")


def content_length(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, list):
        return sum(len(str(item)) for item in value if item)
    if isinstance(value, dict):
        return sum(len(str(key)) + len(str(val)) for key, val in value.items() if val)
    return len(str(value))


def debug_paragraph(diagnostics: RenderDiagnostics, styles: dict[str, ParagraphStyle]) -> Paragraph:
    reasons = "; ".join(diagnostics.skipped_reasons[:8]) or "No renderable content blocks were produced."
    message = (
        "<b>Template render diagnostic</b><br/>"
        f"All content sections were skipped. section_count={diagnostics.section_count}, "
        f"rendered_section_count={diagnostics.rendered_section_count}, "
        f"skipped_section_count={diagnostics.skipped_section_count}.<br/>"
        f"Reasons: {reasons}"
    )
    return Paragraph(message, styles["body"])
    try:
        return colors.HexColor(value)
    except Exception:
        return colors.HexColor("#222222")
