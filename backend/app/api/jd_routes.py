import json
from pathlib import Path
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
import httpx
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_access_type, get_current_user
from app.db.session import get_db
from app.llm.factory import get_llm_provider
from app.models.jd import JD
from app.models.jd_detail import JDDetail
from app.models.jd_template import JDTemplate
from app.models.user import User
from app.schemas.jd import (
    JDCreate,
    JDGenerateRequest,
    JDListResponse,
    JDPublishRequest,
    JDRefineRequest,
    JDResponse,
    normalize_generated_jd,
)
from app.schemas.template_dsl import TemplateDefinition
from app.services.pdf_service import write_simple_pdf
from app.services.template_dsl_service import generate_template_definition


router = APIRouter(prefix="/api/v1/jds", tags=["JDs"])


class TemplateUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    definition_json: dict | None = None

DEFAULT_TEMPLATE_PROMPT = """Use the Wissen Technology corporate classic JD PDF layout.
Keep the official Wissen logo, use the platform color palette (#0A2246, #1A2D58, #445377, #57CFE4, #FF540A), preserve clean section hierarchy, and render the standardized JD sections with recruiter-friendly spacing."""

GENERATE_SYSTEM = """You are an expert technical recruiter creating a Wissen Technology Job Description.
Convert the supplied hiring context into a recruiter-ready JD and structured hiring intelligence.
Use the same disciplined style as a refinement pass: preserve the user's factual constraints, infer only when strongly supported,
normalize technology names, split mandatory and optional skills, and prioritize hiring-critical requirements.

Return ONLY valid JSON with these keys: title, summary, responsibilities, requirements, nice_to_have, soft_skills,
compensation, about_company, skills, resume_skills, metadata.

metadata should include useful structured fields when explicitly supplied or directly inferable:
department, seniority, work_mode, location, experience_years, experience_min_years, experience_max_years,
must_have_skills, preferred_skills, search_synonyms, skill_weights, industry_or_domain.
Experience extraction rules: populate experience_years only when the input explicitly provides numeric years, preferably
as "Work Experience: 5 to 8 Years" or another clear numeric years phrase. Do not infer experience from Senior, Junior,
Lead, Principal, Architect, Manager, or similar seniority/title keywords. If numeric years are absent, leave
experience_years, experience_min_years, and experience_max_years empty or omitted.
Location extraction rules: populate metadata.location only when the input explicitly supplies a city, geography, or
location field. Do not invent or default location. Remote/hybrid/onsite is work_mode, not job location.
skill_weights must be an object of technical skill to integer 0-100, where core must-have skills are highest,
important adjacent skills are middle, and supporting/nice-to-have skills are lower.
search_synonyms should contain recruiter/ATS synonyms for the technical skills only.

Match this section intent: Job Summary, Experience, Location, Mode of Work, Key Responsibilities,
Qualifications and Required Skills, Good to Have Skills, Soft Skills.
Write a Job Summary with 4-6 informative sentences covering role purpose, technical scope,
delivery expectations, collaboration, and impact. Generate 6-8 responsibilities, 8-10
qualifications/required skills, 3-5 good-to-have skills, and 3-5 soft skills when enough context exists.

Requirements must be technical qualifications only, written like "Strong expertise in Core Java, Java 8+",
"Hands-on experience with Spring Boot", "Working knowledge of SQL / NoSQL databases".
Do not include communication, leadership, problem-solving, work mode, agile process, or standalone skill names in requirements.
Put communication, collaboration, leadership, and problem-solving in soft_skills.
Do not hallucinate salary, location, certifications, tools, or benefits that are not supplied or strongly implied.
Do not repeat the word experience in every requirement. Put overall experience only in metadata.experience_years."""

REFINE_SYSTEM = """You are an expert technical recruiter refining a Wissen Technology Job Description.
Apply the user instruction precisely while preserving the same JSON structure and current factual constraints.
Keep technology names normalized, preserve or improve metadata such as must_have_skills, preferred_skills,
search_synonyms, experience_min_years, experience_max_years, and skill_weights.
Requirements must stay technical-only; move communication, collaboration, leadership, and problem-solving into soft_skills.
Return ONLY valid JSON with the same keys as the current JD."""


def validate_ownership(ownership: str) -> str:
    if ownership not in {"personal", "public"}:
        raise HTTPException(status_code=422, detail="ownership must be 'personal' or 'public'")
    return ownership


def upsert_details(db: Session, jd: JD, *, context: str | None, skills: list[str], resume_skills: list[str], metadata: dict):
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    if not detail:
        detail = JDDetail(jd_id=jd.id)
        db.add(detail)

    detail.context = context
    detail.skills = skills
    detail.resume_skills = resume_skills
    detail.metadata_json = metadata


def strip_jd_score_from_json(content: str | None) -> str | None:
    if not content:
        return content
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return content
    if isinstance(parsed, dict):
        parsed.pop("jd_score", None)
        return json.dumps(parsed)
    return content


def serialize_jd(jd: JD, detail: JDDetail | None = None, creator_name: str | None = None) -> JDResponse:
    return JDResponse(
        id=jd.id,
        title=jd.title,
        content=strip_jd_score_from_json(jd.content),
        ownership=jd.ownership,
        pdf_url=jd.pdf_url,
        created_by=jd.created_by,
        created_by_name=creator_name,
        context=detail.context if detail else None,
        skills=detail.skills if detail and isinstance(detail.skills, list) else [],
        resume_skills=detail.resume_skills if detail and isinstance(detail.resume_skills, list) else [],
        metadata=detail.metadata_json if detail and isinstance(detail.metadata_json, dict) else {},
        created_at=jd.created_at,
        updated_at=jd.updated_at,
    )


def visible_jds_query(db: Session, user: User):
    query = db.query(JD)
    if get_access_type(user, db) == "admin":
        return query
    return query.filter(or_(JD.ownership == "public", JD.created_by == user.id))


def serialize_template(template: JDTemplate) -> dict:
    return {
        "id": f"custom-{template.id}",
        "name": template.name,
        "description": template.description,
        "file_url": template.file_url,
        "definition_json": template.definition_json,
        "version": template.version,
        "prompt": template.prompt,
        "is_custom": True,
        "created_at": template.created_at,
    }


def template_prompt_for_upload(filename: str, extracted_text: str) -> str:
    text_hint = extracted_text[:1800].strip()
    return (
        "Create a reusable Wissen Technology job description PDF template by mimicking the uploaded reference PDF's "
        f"layout, typography rhythm, spacing, section hierarchy, table/list treatment, header/footer structure, and visual formatting. "
        "Do not copy the uploaded company's brand, logo, copyrighted copy, or exact proprietary text. Replace branding with the official Wissen logo and Wissen color palette "
        "(#0A2246 navy dark, #1A2D58 navy medium, #445377 slate blue, #57CFE4 cyan, #FF540A orange accent). "
        "Keep the output suitable for Wissen job descriptions with sections for title, summary, experience, location, responsibilities, requirements, good-to-have skills, and soft skills. "
        f"Reference filename: {filename}. "
        f"Extracted layout/content clues: {text_hint if text_hint else 'No extractable text; infer layout from visual PDF structure during future rendering.'}"
    )


@router.get("", response_model=JDListResponse)
def list_jds(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = visible_jds_query(db, current_user)
    total = query.count()
    jds = query.order_by(JD.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    detail_map = {
        detail.jd_id: detail
        for detail in db.query(JDDetail).filter(JDDetail.jd_id.in_([jd.id for jd in jds] or [0])).all()
    }
    creator_ids = [jd.created_by for jd in jds if jd.created_by]
    creator_map = {
        user.id: user.name
        for user in db.query(User).filter(User.id.in_(creator_ids or [0])).all()
    }
    return JDListResponse(
        items=[serialize_jd(jd, detail_map.get(jd.id), creator_map.get(jd.created_by)) for jd in jds],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=JDResponse, status_code=201)
def create_jd(payload: JDCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = strip_jd_score_from_json(payload.content)

    jd = JD(
        title=payload.title,
        content=content,
        ownership=validate_ownership(payload.ownership),
        pdf_url=payload.pdf_url,
        created_by=current_user.id,
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    upsert_details(
        db,
        jd,
        context=payload.context or payload.content,
        skills=payload.skills,
        resume_skills=payload.resume_skills,
        metadata=payload.metadata,
    )
    db.commit()
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    return serialize_jd(jd, detail, current_user.name)


@router.post("/generate", response_model=dict, status_code=201)
async def generate_jd(payload: JDGenerateRequest):
    try:
        llm = get_llm_provider()
        result = await llm.complete_json(
            system=GENERATE_SYSTEM,
            user=(
                f"Input type: {payload.input_type}\n\n"
                "Generate a polished, standardized JD from the supplied hiring context. "
                "Apply the context precisely, keep unsupported details out, and return the complete JSON structure only.\n\n"
                f"Hiring context:\n{payload.raw_input}"
            ),
            max_tokens=2400,
        )
        normalized = normalize_generated_jd(result)
        enforce_explicit_experience_and_location(payload.raw_input, normalized)
        return normalized
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}") from exc


@router.get("/zoho/job-openings", response_model=dict)
async def list_zoho_job_openings(
    page: int = Query(1, ge=1),
    per_page: int = Query(200, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                settings.ZOHO_JOB_OPENINGS_URL,
                params={"page": page, "per_page": per_page},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or "Zoho Recruit returned an error"
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Zoho Recruit fetch failed: {exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise HTTPException(status_code=502, detail="Zoho Recruit returned an unexpected response")
    return payload


@router.post("/transcribe", response_model=dict)
async def transcribe_voice(file: UploadFile = File(...)):
    try:
        llm = get_llm_provider()
        transcribe = getattr(llm, "transcribe_audio", None)
        if not transcribe:
            raise ValueError("Configured LLM provider does not support audio transcription")
        text = await transcribe(file.filename or "voice-message.webm", await file.read(), file.content_type)
        return {"text": text}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Voice transcription failed: {exc}") from exc


@router.post("/{jd_id}/refine", response_model=dict)
async def refine_jd(jd_id: int, payload: JDRefineRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    stored_jd = visible_jds_query(db, current_user).filter(JD.id == jd_id).first() if jd_id > 0 else None
    current_content = payload.content or (stored_jd.content if stored_jd else None)
    if not current_content:
        raise HTTPException(status_code=404, detail="JD content not found")

    try:
        llm = get_llm_provider()
        result = await llm.complete_json(
            system=REFINE_SYSTEM,
            user=f"Instruction: {payload.instruction}\n\nCurrent JD:\n{current_content}",
            max_tokens=2400,
        )
        return normalize_generated_jd(result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM refinement failed: {exc}") from exc


@router.post("/{jd_id}/publish", response_model=JDResponse)
def publish_jd(jd_id: int, payload: JDPublishRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ownership = validate_ownership(payload.ownership)
    content = payload.content
    parsed_content = None
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            parsed_content = parsed
    except json.JSONDecodeError:
        pass

    jd = visible_jds_query(db, current_user).filter(JD.id == jd_id).first() if jd_id > 0 else None
    if not jd:
        jd = JD(title=payload.title, content=content, ownership=ownership, created_by=current_user.id)
        db.add(jd)
    else:
        jd.title = payload.title
        jd.content = content
        jd.ownership = ownership

    if parsed_content is not None:
        parsed_content.pop("jd_score", None)
        jd.content = json.dumps(parsed_content)
    db.commit()
    db.refresh(jd)
    jd.pdf_url = write_simple_pdf(jd.title, jd.content or "", jd.id)

    upsert_details(
        db,
        jd,
        context=payload.context or (parsed_content.get("summary") if parsed_content is not None else content),
        skills=payload.skills or (parsed_content.get("skills", []) if parsed_content is not None else []),
        resume_skills=payload.resume_skills or (parsed_content.get("resume_skills", []) if parsed_content is not None else []),
        metadata=payload.metadata or (parsed_content.get("metadata", {}) if parsed_content is not None else {}),
    )
    db.commit()
    db.refresh(jd)
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    return serialize_jd(jd, detail, current_user.name)


@router.post("/preview", response_model=dict)
def preview_jd(payload: JDPublishRequest, current_user: User = Depends(get_current_user)):
    try:
        parsed_content = json.loads(payload.content)
        if not isinstance(parsed_content, dict):
            parsed_content = {"summary": payload.content}
    except json.JSONDecodeError:
        parsed_content = {"summary": payload.content}
    parsed_content.pop("jd_score", None)
    preview_key = f"preview-{current_user.id}"
    pdf_url = write_simple_pdf(payload.title, json.dumps(parsed_content), preview_key)
    return {"pdf_url": pdf_url}


@router.put("/{jd_id}", response_model=JDResponse)
def update_jd(jd_id: int, payload: JDCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    jd = visible_jds_query(db, current_user).filter(JD.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    jd.title = payload.title
    jd.content = strip_jd_score_from_json(payload.content)
    jd.ownership = validate_ownership(payload.ownership)
    try:
        parsed_content = json.loads(payload.content or "{}")
        if isinstance(parsed_content, dict) and parsed_content:
            parsed_content.pop("jd_score", None)
            jd.content = json.dumps(parsed_content)
    except json.JSONDecodeError:
        pass
    jd.pdf_url = write_simple_pdf(jd.title, jd.content or "", jd.id)
    upsert_details(
        db,
        jd,
        context=payload.context or payload.content,
        skills=payload.skills,
        resume_skills=payload.resume_skills,
        metadata=payload.metadata,
    )
    db.commit()
    db.refresh(jd)
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    return serialize_jd(jd, detail, current_user.name)


@router.post("/upload", response_model=JDResponse, status_code=201)
async def upload_and_parse_jd(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from io import BytesIO
    from pypdf import PdfReader

    filename = file.filename or ""
    content_type = file.content_type or ""
    
    file_bytes = await file.read()
    
    raw_text = ""
    if filename.lower().endswith(".pdf") or "pdf" in content_type.lower():
        try:
            reader = PdfReader(BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            raw_text = "\n".join(text_parts).strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF file: {e}")
    elif filename.lower().endswith(".txt") or "text" in content_type.lower():
        try:
            raw_text = file_bytes.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read text file: {e}")
    else:
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file format. Please upload a .pdf or .txt file."
        )
        
    if not raw_text:
        raise HTTPException(status_code=400, detail="Uploaded file is empty or contains no readable text.")

    # Call LLM to parse and structure the JD
    try:
        llm = get_llm_provider()
        result = await llm.complete_json(
            system=GENERATE_SYSTEM,
            user=(
                f"Input type: uploaded_jd\n"
                f"Source file: {filename}\n\n"
                "Parse and standardize this JD into the Wissen Technology schema. Preserve the original meaning, "
                "extract structured metadata, normalize technologies, and avoid adding unsupported facts.\n\n"
                f"Hiring context extracted from uploaded file:\n{raw_text}"
            ),
            max_tokens=2400,
        )
        normalized = normalize_generated_jd(result)
        enforce_explicit_experience_and_location(raw_text, normalized)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM parsing failed: {exc}") from exc

    # Create the JD row in database
    jd_title = normalized.get("title") or filename.split(".")[0].replace("_", " ").title()
    content_json = json.dumps(normalized)
    
    jd = JD(
        title=jd_title,
        content=content_json,
        ownership="personal",
        created_by=current_user.id,
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    
    # Generate and save PDF with company template
    jd.pdf_url = write_simple_pdf(jd.title, jd.content, jd.id)
    
    # Save details (skills, metadata)
    upsert_details(
        db,
        jd,
        context=normalized.get("summary") or raw_text[:500],
        skills=normalized.get("skills") or [],
        resume_skills=normalized.get("resume_skills") or [],
        metadata=normalized.get("metadata") or {},
    )
    db.commit()
    db.refresh(jd)
    
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    return serialize_jd(jd, detail, current_user.name)


@router.get("/templates", response_model=dict)
def list_jd_templates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    custom_templates = db.query(JDTemplate).filter(JDTemplate.is_active == True).order_by(JDTemplate.created_at.desc()).all()  # noqa: E712
    return {
        "items": [
            {
                "id": "corporate",
                "name": "Corporate Classic",
                "description": "Standard Wissen presentation",
                "file_url": None,
                "definition_json": None,
                "version": 1,
                "prompt": DEFAULT_TEMPLATE_PROMPT,
                "is_custom": False,
            },
            *[serialize_template(template) for template in custom_templates],
        ]
    }


@router.post("/templates/upload", response_model=dict, status_code=201)
async def upload_jd_template(
    name: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if get_access_type(current_user, db) != "admin":
        raise HTTPException(status_code=403, detail="Only admins can upload JD templates")

    filename = file.filename or "template.pdf"
    content_type = file.content_type or ""
    if not filename.lower().endswith(".pdf") and "pdf" not in content_type.lower():
        raise HTTPException(status_code=400, detail="Template upload must be a PDF")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded template PDF is empty")

    template_dir = Path(settings.UPLOADS_DIR) / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in filename)
    stored_name = f"template-{current_user.id}-{safe_name}"
    stored_path = template_dir / stored_name
    stored_path.write_bytes(file_bytes)

    extracted_text = ""
    try:
        from io import BytesIO
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(file_bytes))
        page_summaries = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            box = page.mediabox
            page_summaries.append(
                f"Page {index}: width={float(box.width):.1f}, height={float(box.height):.1f}\n{text}"
            )
        extracted_text = "\n\n".join(page_summaries).strip()
    except Exception:
        extracted_text = ""

    prompt = template_prompt_for_upload(filename, extracted_text)
    template = JDTemplate(
        name=name.strip(),
        description=description,
        file_url=f"/uploads/templates/{stored_name}",
        prompt=prompt,
        created_by=current_user.id,
    )
    db.add(template)
    db.flush()

    llm = get_llm_provider()
    definition = await generate_template_definition(
        llm=llm,
        filename=filename,
        extracted_context=extracted_text,
        template_name=template.name,
        description=description,
    )
    template.definition_json = definition.model_dump(mode="json")
    template.version = definition.schema_version

    db.commit()
    db.refresh(template)
    return serialize_template(template)


@router.get("/templates/{template_id}", response_model=dict)
def get_jd_template(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    numeric_template_id = parse_template_id(template_id)
    template = db.query(JDTemplate).filter(JDTemplate.id == numeric_template_id, JDTemplate.is_active == True).first()  # noqa: E712
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return serialize_template(template)


@router.put("/templates/{template_id}", response_model=dict)
def update_jd_template(template_id: str, payload: TemplateUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if get_access_type(current_user, db) != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update JD templates")

    numeric_template_id = parse_template_id(template_id)
    template = db.query(JDTemplate).filter(JDTemplate.id == numeric_template_id, JDTemplate.is_active == True).first()  # noqa: E712
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if payload.name is not None:
        template.name = payload.name.strip()
    if payload.description is not None:
        template.description = payload.description
    if payload.definition_json is not None:
        definition = TemplateDefinition.model_validate(payload.definition_json)
        template.definition_json = definition.model_dump(mode="json")
        template.version = template.version + 1
    db.commit()
    db.refresh(template)
    return serialize_template(template)


@router.post("/templates/{template_id}/preview", response_model=dict)
def preview_jd_template(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    numeric_template_id = parse_template_id(template_id)
    template = db.query(JDTemplate).filter(JDTemplate.id == numeric_template_id, JDTemplate.is_active == True).first()  # noqa: E712
    if not template or not isinstance(template.definition_json, dict):
        raise HTTPException(status_code=404, detail="Template definition not found")

    sample = sample_jd_for_template_preview()
    sample["metadata"] = {**sample.get("metadata", {}), "template": f"custom-{template.id}"}
    pdf_url = write_simple_pdf(sample["title"], json.dumps(sample), f"template-preview-{template.id}")
    return {"pdf_url": pdf_url}


@router.delete("/templates/{template_id}", response_model=dict)
def delete_jd_template(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if get_access_type(current_user, db) != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete JD templates")

    numeric_template_id = parse_template_id(template_id)
    template = db.query(JDTemplate).filter(JDTemplate.id == numeric_template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    for path in template_paths_for_cleanup(template):
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except Exception:
            pass
    db.delete(template)
    db.commit()
    return {"deleted": True, "id": f"custom-{numeric_template_id}"}


@router.get("/{jd_id}", response_model=JDResponse)
def get_jd(jd_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    jd = visible_jds_query(db, current_user).filter(JD.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    creator = db.query(User).filter(User.id == jd.created_by).first() if jd.created_by else None
    return serialize_jd(jd, detail, creator.name if creator else None)


@router.delete("/{jd_id}", status_code=204)
def delete_jd(jd_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(JD).filter(JD.id == jd_id)
    if get_access_type(current_user, db) != "admin":
        query = query.filter(JD.created_by == current_user.id)
    jd = query.first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    db.delete(jd)
    db.commit()


def enforce_explicit_experience_and_location(source_text: str, jd: dict) -> None:
    metadata = jd.get("metadata")
    if not isinstance(metadata, dict):
        return

    if not has_explicit_experience(source_text):
        for key in ("experience_years", "experience", "experience_min_years", "experience_max_years"):
            metadata.pop(key, None)

    if not has_explicit_location(source_text):
        metadata.pop("location", None)
        jd.pop("location", None)


def has_explicit_experience(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(r"\bwork\s+experience\s*:\s*\d+(?:\.\d+)?\s*(?:to|-)\s*\d+(?:\.\d+)?\s*(?:years?|yrs?)\b", lowered)
        or re.search(r"\b\d+(?:\.\d+)?\s*(?:to|-)\s*\d+(?:\.\d+)?\s*(?:years?|yrs?)\b", lowered)
        or re.search(r"\b\d+(?:\.\d+)?\+?\s*(?:years?|yrs?)\b", lowered)
    )


def has_explicit_location(text: str) -> bool:
    lowered = text.lower()
    city_terms = (
        "bangalore", "bengaluru", "pune", "mumbai", "chennai", "hyderabad", "delhi",
        "noida", "gurgaon", "gurugram", "kolkata", "ahmedabad", "india", "usa", "uk",
    )
    return bool(
        re.search(r"\b(location|city|based in|office in|work location)\b", lowered)
        or any(term in lowered for term in city_terms)
    )


def template_paths_for_cleanup(template: JDTemplate) -> list[Path]:
    paths: list[Path] = []
    if template.file_url:
        relative = template.file_url.lstrip("/")
        if relative.startswith("uploads/"):
            relative = relative.removeprefix("uploads/")
        paths.append(Path(settings.UPLOADS_DIR) / relative)
    return paths


def parse_template_id(template_id: str) -> int:
    raw_id = str(template_id).replace("custom-", "", 1)
    try:
        return int(raw_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid custom template id") from exc


def sample_jd_for_template_preview() -> dict:
    return {
        "title": "Senior Java Backend Engineer",
        "job_summary": "Wissen Technology is hiring a backend engineer to design and deliver scalable services for enterprise platforms.",
        "summary": "Wissen Technology is hiring a backend engineer to design and deliver scalable services for enterprise platforms. The role involves API design, distributed systems thinking, production quality ownership, and close collaboration with product and delivery teams.",
        "about_company": "Wissen Technology builds high-impact custom software products for global clients across financial services, healthcare, retail, and technology-led industries.",
        "roles_and_responsibilities": [
            "Design and build resilient Java and Spring Boot services.",
            "Own API quality, performance, and production readiness.",
            "Collaborate with cross-functional teams to deliver business outcomes.",
            "Review technical designs and improve engineering standards.",
        ],
        "responsibilities": [
            "Design and build resilient Java and Spring Boot services.",
            "Own API quality, performance, and production readiness.",
            "Collaborate with cross-functional teams to deliver business outcomes.",
            "Review technical designs and improve engineering standards.",
        ],
        "required_skills": ["Java", "Spring Boot", "Microservices", "REST APIs", "SQL"],
        "requirements": ["Java", "Spring Boot", "Microservices", "REST APIs", "SQL"],
        "preferred_skills": ["AWS", "Docker", "Kubernetes"],
        "nice_to_have": ["AWS", "Docker", "Kubernetes"],
        "technical_skills": ["Java", "Spring Boot", "Microservices", "SQL", "Hibernate"],
        "soft_skills": ["Clear communication", "Ownership", "Collaboration"],
        "qualifications": ["B.Tech or equivalent engineering degree", "Strong backend engineering fundamentals"],
        "education": "B.Tech / B.E. / MCA or equivalent",
        "experience": "5 to 8 Years",
        "location": "Bengaluru",
        "employment_type": "Full Time",
        "notice_period": "Immediate to 30 days preferred",
        "salary_range": "As per company standards",
        "benefits": ["Health insurance", "Learning programs", "Flexible hybrid work"],
        "project_details": "Enterprise platform modernization with distributed backend services.",
        "team_details": "Agile product engineering team working with architects, QA, DevOps, and product owners.",
        "industry": "Enterprise Technology",
        "department": "Engineering",
        "reporting_manager": "Engineering Manager",
        "travel_requirements": "Minimal travel as needed for client workshops",
        "work_mode": "Hybrid",
        "certifications": ["AWS certification preferred"],
        "languages": ["English"],
        "selection_process": ["Technical screening", "Architecture discussion", "Managerial round"],
        "additional_information": "Candidates should be comfortable owning production services.",
        "contact_information": "careers@wissen.com",
        "skills": ["Java", "Spring Boot", "Microservices", "SQL"],
        "metadata": {
            "experience_years": "5 to 8 Years",
            "location": "Bengaluru",
            "work_mode": "Hybrid",
            "department": "Engineering",
            "industry_or_domain": "Enterprise Platforms",
            "education": "B.Tech / B.E. / MCA or equivalent",
            "employment_type": "Full Time",
            "notice_period": "Immediate to 30 days preferred",
            "salary_range": "As per company standards",
            "benefits": ["Health insurance", "Learning programs", "Flexible hybrid work"],
            "project_details": "Enterprise platform modernization with distributed backend services.",
            "team_details": "Agile product engineering team.",
            "industry": "Enterprise Technology",
            "reporting_manager": "Engineering Manager",
            "travel_requirements": "Minimal",
            "certifications": ["AWS certification preferred"],
            "languages": ["English"],
            "selection_process": ["Technical screening", "Architecture discussion", "Managerial round"],
            "additional_information": "Comfortable owning production services.",
            "contact_information": "careers@wissen.com",
        },
    }
