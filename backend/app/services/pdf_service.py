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
        if template == "modern":
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
