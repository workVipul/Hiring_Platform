import json
import logging
from importlib import import_module
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
            generate = load_custom_template_generator(template, metadata)
            generate(output_path, title, data, metadata)
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
        # Fallback to corporate classic if something fails
        try:
            from app.services.corporate_template import generate
            generate(output_path, title, data, metadata)
        except Exception as fallback_err:
            logger.error(f"Critical error in fallback PDF generation: {fallback_err}", exc_info=True)
            raise fallback_err

    return f"uploads/{filename}"


def load_custom_template_generator(template_id: str, metadata: dict):
    module_name = metadata.get("template_module_name")
    if not module_name:
        module_name = lookup_custom_template_module(template_id)
    if not module_name:
        raise ValueError(f"Custom template {template_id} does not have a generated Python module")

    safe_module = str(module_name).replace("-", "_")
    if not safe_module.startswith("generated_jd_template_"):
        raise ValueError(f"Invalid custom template module name: {module_name}")

    module = import_module(f"app.services.{safe_module}")
    generate = getattr(module, "generate", None)
    if not callable(generate):
        raise ValueError(f"Custom template module {safe_module} does not expose generate")
    return generate


def lookup_custom_template_module(template_id: str) -> str | None:
    try:
        numeric_id = int(template_id.replace("custom-", "", 1))
    except ValueError:
        return None

    from app.db.session import SessionLocal
    from app.models.jd_template import JDTemplate

    db = SessionLocal()
    try:
        template = db.query(JDTemplate).filter(JDTemplate.id == numeric_id, JDTemplate.is_active == True).first()  # noqa: E712
        return template.module_name if template else None
    finally:
        db.close()
