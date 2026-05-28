from pathlib import Path
from typing import Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.pdf_common import (
    ABOUT_WISSEN,
    WISSEN_SITES,
    as_list,
    format_experience,
    build_wissen_logo_table,
)

def make_tech_heading(text: str, style: Any, bar_color: Any, printable_width: float) -> Table:
    heading_p = Paragraph(text, style)
    # Using Table to draw a beautiful left vertical bar
    heading_table = Table([["", heading_p]], colWidths=[3, printable_width - 10])
    heading_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), bar_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (1, 0), (1, 0), 8),
            ]
        )
    )
    return heading_table

def generate(output_path: Path, title: str, data: dict, metadata: dict) -> None:
    margin_size = 45
    printable_width = 612 - margin_size * 2
    accent_color = colors.HexColor("#1A2D58")
    heading_color = colors.HexColor("#0A2246")

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=margin_size,
        leftMargin=margin_size,
        topMargin=margin_size,
        bottomMargin=margin_size,
    )

    story = []

    # Logo
    logo_table = build_wissen_logo_table(printable_width)
    if logo_table:
        story.append(logo_table)

    # Thick Line Table
    line_table = Table([[""]], colWidths=[printable_width], rowHeights=[3.5])
    line_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 2.5, accent_color),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.extend([line_table, Spacer(1, 12)])

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TechTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=accent_color,
        spaceAfter=15,
    )
    heading_style = ParagraphStyle(
        "TechHeading",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=10,
        leading=13,
        textColor=heading_color,
        spaceBefore=0,
        spaceAfter=0,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "TechBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#222222"),
        spaceAfter=8,
    )
    bullet_style = ParagraphStyle(
        "TechBullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#222222"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    story.append(Paragraph(f"Wissen Technology is hiring for {title}", title_style))
    story.append(Spacer(1, 8))

    # Add custom heading layout
    def add_tech_section(heading: str, value: Any):
        if not value:
            return
        story.append(make_tech_heading(heading, heading_style, accent_color, printable_width))
        story.append(Spacer(1, 6)) # spacer between heading and section content
        if isinstance(value, list):
            for item in value:
                if str(item).strip():
                    story.append(Paragraph(f"&bull; {item}", bullet_style))
        elif isinstance(value, dict):
            for key, val in value.items():
                label = str(key).replace("_", " ").title()
                story.append(Paragraph(f"<b>{label}</b>: {val}", body_style))
        else:
            story.append(Paragraph(str(value), body_style))
        story.append(Spacer(1, 6)) # spacer after section content

    # Add sections
    add_tech_section("About Wissen Technology", ABOUT_WISSEN)

    metadata = data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}
    add_tech_section("Job Summary", data.get("summary") or data.get("content"))
    add_tech_section("Experience", format_experience(metadata.get("experience_years") or metadata.get("experience") or data.get("experience")))
    add_tech_section("Location", metadata.get("location") or data.get("location"))
    add_tech_section("Mode of Work", metadata.get("work_mode") or data.get("work_mode"))
    add_tech_section("Key Responsibilities", data.get("responsibilities"))
    
    required = as_list(data.get("requirements"))
    if not required:
        required = [f"Strong expertise in {skill}" for skill in as_list(data.get("skills"))]
    add_tech_section("Qualifications and Required Skills", required)
    add_tech_section("Good to Have Skills", data.get("nice_to_have") or data.get("good_to_have"))
    add_tech_section("Soft Skills", data.get("soft_skills") or data.get("resume_skills"))

    # Wissen Sites
    story.append(make_tech_heading("Wissen Sites", heading_style, accent_color, printable_width))
    story.append(Spacer(1, 6))
    for label, display_url, href_url in WISSEN_SITES:
        link_html = f"&bull; <b>{label}</b>: <font color='#0066cc'><a href='{href_url}'>{display_url}</a></font>"
        story.append(Paragraph(link_html, bullet_style))

    doc.build(story)
