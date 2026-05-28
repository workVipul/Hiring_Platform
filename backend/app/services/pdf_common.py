import re
from pathlib import Path
from typing import Any
from reportlab.lib import colors
from reportlab.platypus import Image, Paragraph, Table, TableStyle

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

def build_wissen_logo_table(printable_width: float, align: str = "LEFT") -> Table:
    logo_path = Path(__file__).parent.parent / "wissen_logo.png"
    if logo_path.exists():
        logo_img = Image(str(logo_path), width=130, height=35)
        logo_table = Table([[logo_img]], colWidths=[printable_width])
        logo_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), align),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return logo_table
    return None

def build_sections_story(story: list, data: dict, heading_style: Any, body_style: Any, bullet_style: Any):
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
