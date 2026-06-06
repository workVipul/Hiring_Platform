import ast
from importlib import import_module, invalidate_caches
import re
from pathlib import Path

from app.llm.base import LLMProvider


SYSTEM_PROMPT = """You generate reusable ReportLab PDF template modules for a hiring platform.
Return ONLY JSON with one key: "code".
The code must be a complete Python module that defines:
def generate(output_path: Path, title: str, data: dict, metadata: dict) -> None

Rules:
- Use ReportLab only, matching the conventions of the existing template modules.
- Import Path from pathlib.
- Import colors, letter, ParagraphStyle, getSampleStyleSheet, and ReportLab platypus classes as needed.
- Reuse app.services.pdf_common helpers when useful: ABOUT_WISSEN, WISSEN_SITES, as_list, build_wissen_logo_table, format_experience.
- Do not read files, call network APIs, inspect environment variables, execute subprocesses, use eval/exec/compile, or import unsafe modules.
- Do not include markdown fences.
- The generated module must be reusable for any JD data and must write the PDF to output_path.
- Preserve the uploaded reference's layout direction, spacing rhythm, section ordering, colors, headings, divider style, tables/lists, and overall appearance as much as possible.
- Replace uploaded branding with Wissen branding and logo helpers."""


def build_user_prompt(filename: str, extracted_text: str) -> str:
    return (
        f"Uploaded reference PDF filename: {filename}\n\n"
        "Extracted PDF text and layout clues follow. Infer a reusable JD template from this reference. "
        "Use the reference for visual styling, section hierarchy, spacing, typography rhythm, color usage, and layout, "
        "but render generated Wissen JD content from the data/metadata arguments.\n\n"
        f"{extracted_text[:6000] if extracted_text.strip() else 'No extractable text was available from the PDF. Generate a clean visual template that can mimic a structured uploaded JD reference while preserving Wissen branding.'}"
    )


async def generate_template_module(
    *,
    llm: LLMProvider,
    filename: str,
    extracted_text: str,
    template_id: int,
    template_name: str,
    services_dir: Path,
) -> str:
    result = await llm.complete_json(
        system=SYSTEM_PROMPT,
        user=build_user_prompt(filename, extracted_text),
        max_tokens=6000,
    )
    code = strip_code_fence(str(result.get("code", "")).strip())
    if not code:
        raise ValueError("LLM did not return template code")

    module_name = f"generated_jd_template_{template_id}_{slugify(template_name)}"
    module_path = services_dir / f"{module_name}.py"
    validate_template_code(code)
    module_path.write_text(code, encoding="utf-8")
    invalidate_caches()
    try:
        module = import_module(f"app.services.{module_name}")
    except Exception:
        module_path.unlink(missing_ok=True)
        raise
    if not callable(getattr(module, "generate", None)):
        module_path.unlink(missing_ok=True)
        raise ValueError("Generated template module does not expose a callable generate function")
    return module_name


def validate_template_code(code: str) -> None:
    tree = ast.parse(code)
    has_generate = False
    blocked_import_roots = {"os", "sys", "subprocess", "socket", "requests", "httpx", "urllib", "importlib", "builtins"}
    blocked_calls = {"eval", "exec", "compile", "open", "__import__", "input"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in blocked_import_roots:
                    raise ValueError(f"Generated template imports blocked module: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in blocked_import_roots:
                raise ValueError(f"Generated template imports blocked module: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in blocked_calls:
                raise ValueError(f"Generated template uses blocked call: {node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in blocked_calls:
                raise ValueError(f"Generated template uses blocked call: {node.func.attr}")
        elif isinstance(node, ast.FunctionDef) and node.name == "generate":
            has_generate = True

    if not has_generate:
        raise ValueError("Generated template must define generate(output_path, title, data, metadata)")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:48] or "template"


def strip_code_fence(code: str) -> str:
    if code.startswith("```python"):
        code = code.removeprefix("```python").strip()
    elif code.startswith("```"):
        code = code.removeprefix("```").strip()
    if code.endswith("```"):
        code = code.removesuffix("```").strip()
    return code
