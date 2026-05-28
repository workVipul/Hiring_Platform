from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.pdf_common import (
    ABOUT_WISSEN,
    WISSEN_SITES,
    build_sections_story,
    build_wissen_logo_table,
)

def generate(output_path: Path, title: str, data: dict, metadata: dict) -> None:
    margin_size = 36
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

    # Right-aligned Logo
    logo_table = build_wissen_logo_table(printable_width, align="RIGHT")
    if logo_table:
        story.append(logo_table)

    # Compact Line Table
    line_table = Table([[""]], colWidths=[printable_width], rowHeights=[1.5])
    line_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 1.0, accent_color),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.extend([line_table, Spacer(1, 8)])

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ModTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=accent_color,
        spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "ModHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=heading_color,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ModBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#222222"),
        spaceAfter=5,
    )
    bullet_style = ParagraphStyle(
        "ModBullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#222222"),
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3,
    )

    story.append(Paragraph(f"Wissen Technology is hiring for {title}", title_style))
    story.append(Spacer(1, 4))

    # Add sections
    story.append(Paragraph("About Wissen Technology", heading_style))
    story.append(Paragraph(ABOUT_WISSEN, body_style))

    build_sections_story(story, data, heading_style, body_style, bullet_style)

    # Wissen Sites
    story.append(Paragraph("Wissen Sites", heading_style))
    for label, display_url, href_url in WISSEN_SITES:
        link_html = f"&bull; <b>{label}</b>: <font color='#0066cc'><a href='{href_url}'>{display_url}</a></font>"
        story.append(Paragraph(link_html, bullet_style))

    doc.build(story)
