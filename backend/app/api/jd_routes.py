import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_access_type, get_current_user
from app.db.session import get_db
from app.llm.factory import get_llm_provider
from app.models.jd import JD
from app.models.jd_detail import JDDetail
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
from app.services.pdf_service import write_simple_pdf


router = APIRouter(prefix="/api/v1/jds", tags=["JDs"])

GENERATE_SYSTEM = """You are an expert technical recruiter creating a Wissen Technology Job Description.
Convert the supplied hiring context into a recruiter-ready JD and structured hiring intelligence.
Use the same disciplined style as a refinement pass: preserve the user's factual constraints, infer only when strongly supported,
normalize technology names, detect seniority, split mandatory and optional skills, and prioritize hiring-critical requirements.

Return ONLY valid JSON with these keys: title, summary, responsibilities, requirements, nice_to_have, soft_skills,
compensation, about_company, skills, resume_skills, metadata.

metadata should include useful structured fields when inferable:
department, seniority, work_mode, location, experience_years, experience_min_years, experience_max_years,
must_have_skills, preferred_skills, search_synonyms, skill_weights, industry_or_domain.
Experience extraction rules: "5 years" means min 5 and max 10; "5-10 years" means min 5 and max 10;
"3+ years" means min 3 and max 8; "less than 5 years" means min 0 and max 5. Keep experience_years as a readable
phrase such as "4+ years" or "5-10 years".
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


@router.get("/{jd_id}", response_model=JDResponse)
def get_jd(jd_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    jd = visible_jds_query(db, current_user).filter(JD.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    creator = db.query(User).filter(User.id == jd.created_by).first() if jd.created_by else None
    return serialize_jd(jd, detail, creator.name if creator else None)


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
        return normalize_generated_jd(result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}") from exc


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
