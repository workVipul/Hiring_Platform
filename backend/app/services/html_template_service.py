import json
import logging
import re
from html import escape
from html.parser import HTMLParser
from typing import Any, Sequence

from app.llm.base import LLMProvider

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
  "mapped_fields": ["title", "job_summary"]
}}

The uploaded PDF is NOT content. It is ONLY a visual design reference.

Analyze:
- layout, typography, colors, spacing
- columns, CSS grid/flex structure
- sidebars, banners, headers, footers
- tables, label/value rows, section ordering

Generate maintainable semantic HTML using these regions where appropriate:
header, sidebar via aside, main, footer, section.

Use modern CSS Flexbox/Grid. Do not generate huge nested tables. Use tables only when the visual design has a true table or label/value grid.

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
- Use @page for page size/margins when useful.
- Return reusable HTML and CSS only, not a complete PDF.
- mapped_fields must list every placeholder used in html."""


def build_html_template_user_prompt(filename: str, page_count: int) -> str:
    return (
        f"Uploaded reference PDF filename: {filename}\n"
        f"Rendered PDF pages provided as images: {page_count}\n\n"
        "Create a reusable HTML/CSS template for future Wissen job descriptions. "
        "The uploaded PDF is a visual reference only; use placeholders for JD data."
    )


async def generate_html_template(
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
    if isinstance(result, dict) and "template" in result and isinstance(result["template"], dict):
        result = result["template"]
    if not isinstance(result, dict):
        raise ValueError("HTML template response was not a JSON object")

    html = sanitize_template_html(str(result.get("html") or ""))
    css = sanitize_template_css(str(result.get("css") or ""))
    mapped_fields = normalize_mapped_fields(result.get("mapped_fields"), html)
    validate_html_template(html, css, mapped_fields)

    logger.warning("TEMPLATE_HTML_LENGTH=%s", len(html))
    logger.warning("TEMPLATE_CSS_LENGTH=%s", len(css))
    logger.warning("MAPPED_FIELDS=%s", mapped_fields)
    return {"html": html, "css": css, "mapped_fields": mapped_fields}


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
