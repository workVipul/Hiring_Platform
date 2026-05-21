import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, KeepTogether, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)

# Standard company content
ABOUT_WISSEN = (
    "At Wissen Technology, we deliver niche, custom-built products that solve complex business "
    "challenges across industries worldwide. Founded in 2015, our core philosophy is built around a "
    "strong product engineering mindset—ensuring every solution is architected and delivered right the "
    "first time. Today, Wissen Technology has a global footprint with 2000+ employees across offices in "
    "the US, UK, UAE, India, and Australia. Our commitment to excellence translates into delivering 2X "
    "impact compared to traditional service providers. How do we achieve this? Through a combination of "
    "deep domain knowledge, cutting-edge technology expertise, and a relentless focus on quality. We "
    "don't just meet expectations—we exceed them by ensuring faster time-to-market, reduced rework, and "
    "greater alignment with client objectives. We have a proven track record of building mission-"
    "critical systems across industries, including financial services, healthcare, retail, manufacturing, "
    "and more. Wissen stands apart through its unique delivery models. Our outcome-based projects "
    "ensure predictable costs and timelines, while our agile pods provide clients the flexibility to adapt "
    "to their evolving business needs. Wissen leverages its thought leadership and technology prowess to "
    "drive superior business outcomes. Our success is powered by top-tier talent. Our mission is clear: "
    "to be the partner of choice for building world-class custom products that deliver exceptional "
    "impact—the first time, every time."
)

WISSEN_SITES = [
    ("Website", "www.wissen.com", "https://www.wissen.com"),
    ("LinkedIn", "linkedin.com/company/wissen-technology", "https://www.linkedin.com/company/wissen-technology"),
    ("Wissen Leadership", "linkedin.com/company/leadership-team", "https://www.linkedin.com/company/leadership-team/"),
    ("Wissen Live", "linkedin.com/company/wissen-technology/posts/?feedView=All", "https://www.linkedin.com/company/wissen-technology/posts/?feedView=All"),
    ("Wissen Thought Leadership", "wissen.com/articles", "https://www.wissen.com/articles/"),
]

def write_simple_pdf(title: str, content: str, jd_id: int) -> str:
    uploads_dir = Path(settings.UPLOADS_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"generated-jd-{jd_id}.pdf"
    output_path = uploads_dir / filename

    # Parse content
    try:
        data = json.loads(content)
    except Exception:
        data = {"content": content}

    # Setup document: letter size with 0.75 inch margins (54 points)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    story = []
    
    # 1. Company Logo - backend/app/wissen_logo.png
    logo_path = Path(__file__).parent.parent / "wissen_logo.png"
    if logo_path.exists():
        logo_img = Image(str(logo_path), width=130, height=35)
        # Put inside borderless table to align left
        logo_table = Table([[logo_img]], colWidths=[504])
        logo_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(logo_table)
    
    # Decorative line under logo
    line_data = [['']]
    line_table = Table(line_data, colWidths=[504], rowHeights=[2])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor("#0b3c5d")),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 15))

    # Styles
    styles = getSampleStyleSheet()
    
    title_text = f"Wissen Technology is hiring for {title}"
    title_style = ParagraphStyle(
        'WissenTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0b3c5d"),
        spaceAfter=15
    )
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 8))

    # Heading styles
    heading_style = ParagraphStyle(
        'WissenHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0b3c5d"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'WissenBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14.0,
        textColor=colors.HexColor("#333333"),
        spaceAfter=8
    )
    
    bullet_style = ParagraphStyle(
        'WissenBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14.0,
        textColor=colors.HexColor("#333333"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    def add_section(heading: str, value: Any):
        if not value:
            return
        story.append(Paragraph(heading, heading_style))
        if isinstance(value, list):
            for item in value:
                if str(item).strip():
                    story.append(Paragraph(f"&bull; {item}", bullet_style))
        elif isinstance(value, dict):
            for k, v in value.items():
                label = k.replace("_", " ").title()
                story.append(Paragraph(f"<b>{label}</b>: {v}", body_style))
        else:
            story.append(Paragraph(str(value), body_style))

    # 2. About Wissen Technology (Standard Section)
    add_section("About Wissen Technology", ABOUT_WISSEN)

    # 3. Job Summary
    summary_text = ""
    if isinstance(data, dict):
        summary_text = data.get("summary") or data.get("content")
    else:
        summary_text = str(data)
    add_section("Job Summary", summary_text)

    # 4. Experience
    exp_text = ""
    if isinstance(data, dict):
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            exp_text = metadata.get("experience_years") or metadata.get("experience")
        if not exp_text:
            exp_text = data.get("experience") or data.get("experience_level")
    
    if exp_text:
        add_section("Experience", exp_text)

    # 5. Required Skills / Good to Have Skills
    skills_list = []
    if isinstance(data, dict):
        skills_list = data.get("skills") or data.get("requirements")
    
    if isinstance(skills_list, list) and skills_list:
        add_section("Good to Have Skills", skills_list)
    elif isinstance(skills_list, str) and skills_list:
        add_section("Good to Have Skills", [s.strip() for s in skills_list.split(",") if s.strip()])

    # 6. Soft Skills
    soft_skills = None
    if isinstance(data, dict):
        soft_skills = data.get("soft_skills") or data.get("nice_to_have")
    if soft_skills:
        add_section("Soft Skills", soft_skills)

    # 7. Wissen Sites (Standard Section)
    story.append(Paragraph("Wissen Sites", heading_style))
    for label, display_url, href_url in WISSEN_SITES:
        link_html = f"&bull; <b>{label}</b>: <font color='#0066cc'><a href='{href_url}'>{display_url}</a></font>"
        story.append(Paragraph(link_html, bullet_style))

    # Build document
    doc.build(story)
    
    return f"uploads/{filename}"
