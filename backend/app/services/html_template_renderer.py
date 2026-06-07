import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

from app.services.dynamic_template_renderer import build_field_data
from app.services.html_template_service import ALLOWED_TEMPLATE_FIELDS, extract_placeholders, sanitize_template_css

logger = logging.getLogger(__name__)


class HtmlTemplateRenderer:
    def __init__(self, template_html: str, template_css: str, mapped_fields: list[str] | None = None):
        self.template_html = template_html
        self.template_css = sanitize_template_css(template_css)
        self.mapped_fields = mapped_fields or extract_placeholders(template_html)

    def render_pdf(self, output_path: Path, title: str, data: dict[str, Any], metadata: dict[str, Any]) -> None:
        html = self.render_html(title, data, metadata)
        try:
            from weasyprint import HTML
        except OSError as exc:
            raise RuntimeError(
                "WeasyPrint native dependencies are not installed or not on PATH. "
                "Install GTK/Pango runtime libraries for this OS before rendering custom HTML templates."
            ) from exc
        HTML(string=html, base_url=str(output_path.parent.resolve())).write_pdf(str(output_path))

    def render_html(self, title: str, data: dict[str, Any], metadata: dict[str, Any]) -> str:
        field_data = build_field_data(title, data, metadata)
        context = {field: format_template_value(field_data.get(field)) for field in ALLOWED_TEMPLATE_FIELDS}
        for field in self.mapped_fields:
            context.setdefault(field, "")

        logger.warning("HTML_TEMPLATE_RENDER_FIELDS=%s", sorted(field for field in self.mapped_fields if context.get(field)))
        env = Environment(
            autoescape=select_autoescape(default=True, default_for_string=True),
            undefined=StrictUndefined,
        )
        template = env.from_string(self.template_html)
        body = template.render(**context)
        return (
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<style>{self.template_css}</style>"
            "</head><body>"
            f"{body}"
            "</body></html>"
        )


def format_template_value(value: Any) -> Markup | str:
    if value is None:
        return ""
    if isinstance(value, list):
        items = "".join(f"<li>{escape(str(item))}</li>" for item in value if str(item).strip())
        return Markup(f"<ul>{items}</ul>") if items else ""
    if isinstance(value, dict):
        rows = "".join(
            f"<tr><th>{escape(str(key).replace('_', ' ').title())}</th><td>{escape(str(val))}</td></tr>"
            for key, val in value.items()
            if val
        )
        return Markup(f"<table>{rows}</table>") if rows else ""
    return str(value)
