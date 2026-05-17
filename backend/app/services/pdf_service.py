import json
import textwrap
from pathlib import Path
from typing import Any

from app.core.config import settings


def content_to_lines(title: str, content: str) -> list[str]:
    lines = [title, ""]
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"content": content}

    if isinstance(data, dict):
        for key, value in data.items():
            if key == "title":
                continue
            label = key.replace("_", " ").title()
            lines.append(label)
            lines.extend(format_value(value))
            lines.append("")
    else:
        lines.extend(format_value(data))

    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(str(line), width=88) or [""])
    return wrapped


def format_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [f"- {item}" for item in value]
    if isinstance(value, dict):
        rows: list[str] = []
        for key, item in value.items():
            rows.append(f"{key.replace('_', ' ').title()}: {item}")
        return rows
    return [str(value)]


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(title: str, content: str, jd_id: int) -> str:
    uploads_dir = Path(settings.UPLOADS_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"generated-jd-{jd_id}.pdf"
    output_path = uploads_dir / filename

    lines = content_to_lines(title, content)
    text_commands = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
    for idx, line in enumerate(lines[:52]):
        safe = escape_pdf_text(line)
        if idx == 0:
            text_commands.extend(["/F1 16 Tf", f"({safe}) Tj", "/F1 11 Tf", "T*"])
        else:
            text_commands.extend([f"({safe}) Tj", "T*"])
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )

    output_path.write_bytes(pdf)
    return f"uploads/{filename}"
