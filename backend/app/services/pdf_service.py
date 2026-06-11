import json
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

def write_simple_pdf(title: str, content: str, jd_id: int | str) -> str:
    uploads_dir = Path(settings.UPLOADS_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"generated-jd-{jd_id}.pdf"
    output_path = uploads_dir / filename

    try:
        data = json.loads(content)
    except Exception:
        data = {"summary": content}

    # Extract template choice from metadata
    template = "default"
    metadata = {}
    if isinstance(data, dict):
        metadata = data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}
        template = metadata.get("template", "default").lower()

    # Route to the appropriate template module
    try:
        if template.startswith("custom-"):
            custom_template = lookup_custom_template(template)
            if not custom_template:
                raise ValueError(f"Custom template {template} was not found")
            if not settings.ENABLE_LEGACY_DSL:
                from app.services.html_template_renderer import HtmlTemplateRenderer

                template_html = custom_template.get("template_html")
                template_css = custom_template.get("template_css")
                if not template_html or not template_css:
                    raise ValueError(f"Custom template {template} does not have HTML/CSS template data")
                renderer = HtmlTemplateRenderer(
                    template_html=template_html,
                    template_css=template_css,
                    mapped_fields=custom_template.get("mapped_fields") or [],
                )
                renderer.render_pdf(output_path, title, data, metadata)
            else:
                from app.services.dynamic_template_renderer import render_dynamic_template

                definition = custom_template.get("definition_json")
                if not definition:
                    raise ValueError(f"Custom template {template} does not have a JSON definition")
                render_dynamic_template(output_path, title, data, metadata, definition)
        elif template == "modern":
            from app.services.modern_template import generate
            generate(output_path, title, data, metadata)
        elif template == "executive":
            from app.services.executive_template import generate
            generate(output_path, title, data, metadata)
        elif template == "tech":
            from app.services.tech_template import generate
            generate(output_path, title, data, metadata)
        else:  # corporate or default
            from app.services.corporate_template import generate
            generate(output_path, title, data, metadata)
    except Exception as e:
        logger.error(f"Error generating PDF using template '{template}': {e}", exc_info=True)
        if template.startswith("custom-"):
            raise
        # Fallback to corporate classic if something fails
        try:
            from app.services.corporate_template import generate
            generate(output_path, title, data, metadata)
        except Exception as fallback_err:
            logger.error(f"Critical error in fallback PDF generation: {fallback_err}", exc_info=True)
            raise fallback_err

    return f"uploads/{filename}"


def lookup_custom_template(template_id: str) -> dict | None:
    try:
        numeric_id = int(template_id.replace("custom-", "", 1))
    except ValueError:
        return None

    from app.db.session import SessionLocal
    from app.models.jd_template import JDTemplate

    db = SessionLocal()
    try:
        template = db.query(JDTemplate).filter(JDTemplate.id == numeric_id, JDTemplate.is_active == True).first()  # noqa: E712
        if not template:
            return None
        return {
            "definition_json": template.definition_json,
            "template_html": template.template_html,
            "template_css": template.template_css,
            "mapped_fields": template.mapped_fields if isinstance(template.mapped_fields, list) else [],
            "layout_metadata": template.layout_metadata if isinstance(template.layout_metadata, dict) else {},
        }
    finally:
        db.close()


def lookup_custom_template_definition(template_id: str) -> dict | None:
    template = lookup_custom_template(template_id)
    return template.get("definition_json") if template else None
