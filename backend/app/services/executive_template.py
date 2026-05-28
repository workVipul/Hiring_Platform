from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.pdf_common import (
    ABOUT_WISSEN,
    WISSEN_SITES,
    build_sections_story,
    build_wissen_logo_table,
)

def generate(output_path: Path, title: str, data: dict, metadata: dict) -> None:
    margin_size = 54
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

    # Centered Logo
    logo_table = build_wissen_logo_table(printable_width, align="CENTER")
    if logo_table:
        story.append(logo_table)

    # Double Line Table
    line_table = Table([[""]], colWidths=[printable_width], rowHeights=[4.0])
    line_table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (-1, -1), 0.75, accent_color),
                ("LINEBELOW", (0, 0), (-1, -1), 0.75, accent_color),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.extend([line_table, Spacer(1, 15)])

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExecTitle",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=16,
        leading=20,
        alignment=1, # Center
        textColor=accent_color,
        spaceAfter=15,
    )
    heading_style = ParagraphStyle(
        "ExecHeading",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=11,
        leading=14,
        textColor=heading_color,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ExecBody",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2d3748"),
        spaceAfter=8,
    )
    bullet_style = ParagraphStyle(
        "ExecBullet",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2d3748"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    story.append(Paragraph(f"Wissen Technology is hiring for {title}", title_style))
    story.append(Spacer(1, 8))

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
