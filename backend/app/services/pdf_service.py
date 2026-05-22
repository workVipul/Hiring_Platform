import json
import logging
import re
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings

logger = logging.getLogger(__name__)

ABOUT_WISSEN = (
    "At Wissen Technology, we deliver niche, custom-built products that solve complex business "
    "challenges across industries worldwide. Founded in 2015, our core philosophy is built around a "
    "strong product engineering mindset - ensuring every solution is architected and delivered right "
    "the first time. Today, Wissen Technology has a global footprint with 2000+ employees across "
    "offices in the US, UK, UAE, India, and Australia. Our commitment to excellence translates into "
    "delivering 2X impact compared to traditional service providers. How do we achieve this? Through "
    "a combination of deep domain knowledge, cutting-edge technology expertise, and a relentless focus "
    "on quality. We don't just meet expectations - we exceed them by ensuring faster time-to-market, "
    "reduced rework, and greater alignment with client objectives. We have a proven track record of "
    "building mission-critical systems across industries, including financial services, healthcare, "
    "retail, manufacturing, and more. Wissen stands apart through its unique delivery models. Our "
    "outcome-based projects ensure predictable costs and timelines, while our agile pods provide "
    "clients the flexibility to adapt to their evolving business needs. Wissen leverages its thought "
    "leadership and technology prowess to drive superior business outcomes. Our success is powered by "
    "top-tier talent. Our mission is clear: to be the partner of choice for building world-class custom "
    "products that deliver exceptional impact - the first time, every time."
)

WISSEN_SITES = [
    ("Website", "www.wissen.com", "https://www.wissen.com"),
    ("LinkedIn", "linkedin.com/company/wissen-technology", "https://www.linkedin.com/company/wissen-technology"),
    ("Wissen Leadership", "linkedin.com/company/leadership-team", "https://www.linkedin.com/company/leadership-team/"),
    ("Wissen Live", "linkedin.com/company/wissen-technology/posts/?feedView=All", "https://www.linkedin.com/company/wissen-technology/posts/?feedView=All"),
    ("Wissen Thought Leadership", "wissen.com/articles", "https://www.wissen.com/articles/"),
]


def write_simple_pdf(title: str, content: str, jd_id: int | str) -> str:
    uploads_dir = Path(settings.UPLOADS_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"generated-jd-{jd_id}.pdf"
    output_path = uploads_dir / filename

    try:
        data = json.loads(content)
    except Exception:
        data = {"summary": content}

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    story = []
    logo_path = Path(__file__).parent.parent / "wissen_logo.png"
    if logo_path.exists():
        logo_img = Image(str(logo_path), width=130, height=35)
        logo_table = Table([[logo_img]], colWidths=[504])
        logo_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(logo_table)

    line_table = Table([[""]], colWidths=[504], rowHeights=[2])
    line_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 1.5, colors.HexColor("#0b3c5d")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.extend([line_table, Spacer(1, 15)])

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "WissenTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0b3c5d"),
        spaceAfter=15,
    )
    heading_style = ParagraphStyle(
        "WissenHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0b3c5d"),
        spaceBefore=11,
        spaceAfter=6,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "WissenBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#222222"),
        spaceAfter=8,
    )
    bullet_style = ParagraphStyle(
        "WissenBullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#222222"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4,
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
            for key, val in value.items():
                label = str(key).replace("_", " ").title()
                story.append(Paragraph(f"<b>{label}</b>: {val}", body_style))
        else:
            story.append(Paragraph(str(value), body_style))

    def as_list(value: Any) -> list[Any]:
        if not value:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def format_experience(value: Any) -> Any:
        if value is None or value == "":
            return value
        text = str(value).strip()
        if re.fullmatch(r"\d+(\.\d+)?", text):
            return f"{text} years"
        return text

    story.append(Paragraph(f"Wissen Technology is hiring for {title}", title_style))
    story.append(Spacer(1, 8))

    add_section("About Wissen Technology", ABOUT_WISSEN)

    if isinstance(data, dict):
        metadata = data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}
        add_section("Job Summary", data.get("summary") or data.get("content"))
        add_section("Experience", format_experience(metadata.get("experience_years") or metadata.get("experience") or data.get("experience")))
        add_section("Location", metadata.get("location") or data.get("location"))
        add_section("Mode of Work", metadata.get("work_mode") or data.get("work_mode"))
        add_section("Key Responsibilities", data.get("responsibilities"))
        required = as_list(data.get("requirements"))
        if not required:
            required = [f"Strong expertise in {skill}" for skill in as_list(data.get("skills"))]
        add_section("Qualifications and Required Skills", required)
        add_section("Good to Have Skills", data.get("nice_to_have") or data.get("good_to_have"))
        add_section("Soft Skills", data.get("soft_skills") or data.get("resume_skills"))
    else:
        add_section("Job Summary", str(data))

    story.append(Paragraph("Wissen Sites", heading_style))
    for label, display_url, href_url in WISSEN_SITES:
        link_html = f"&bull; <b>{label}</b>: <font color='#0066cc'><a href='{href_url}'>{display_url}</a></font>"
        story.append(Paragraph(link_html, bullet_style))

    doc.build(story)
    return f"uploads/{filename}"
