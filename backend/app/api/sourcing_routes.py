import json
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.security import get_access_type, get_current_user
from app.db.session import get_db
from app.models.jd import JD
from app.models.jd_detail import JDDetail
from app.models.user import User
from app.services.zoho_service import ZohoRecruitService
from app.services.ranking_service import CandidateRankingEngine

router = APIRouter(prefix="/api/v1/sourcing", tags=["Sourcing"])

class SourcingRequest(BaseModel):
    jd_id: int
    page: int = 1
    per_page: int = 20
    skills: list[str] | None = None
    location: str | None = None
    seniority: str | None = None
    all_candidates: bool = False

def visible_jd(db: Session, user: User, jd_id: int):
    query = db.query(JD).filter(JD.id == jd_id)
    if get_access_type(user, db) != "admin":
        query = query.filter(or_(JD.ownership == "public", JD.created_by == user.id))
    return query.first()


def merge_candidates(existing: list[dict], incoming: list[dict]) -> list[dict]:
    seen = {str(candidate.get("id")) for candidate in existing}
    merged = [*existing]
    for candidate in incoming:
        candidate_id = str(candidate.get("id"))
        if candidate_id and candidate_id not in seen:
            merged.append(candidate)
            seen.add(candidate_id)
    return merged


def filter_attempts(skills: list[str], location: str | None) -> list[dict]:
    attempts = [
        {
            "label": "Skills + location",
            "skills": skills,
            "location": location,
            "seniority": None,
        },
        {
            "label": "Skills only",
            "skills": skills,
            "location": None,
            "seniority": None,
        },
    ]
    unique_attempts = []
    seen = set()
    for attempt in attempts:
        key = (
            tuple(attempt["skills"]),
            attempt["location"] or "",
        )
        if key not in seen and attempt["skills"]:
            unique_attempts.append(attempt)
            seen.add(key)
    return unique_attempts


def jd_for_ranking(jd: JD, experience_or_seniority: str | None):
    if not experience_or_seniority:
        return jd
    try:
        content = json.loads(jd.content or "{}")
    except json.JSONDecodeError:
        content = {}
    if not isinstance(content, dict):
        content = {}
    metadata = content.get("metadata") if isinstance(content.get("metadata"), dict) else {}
    metadata = {**metadata}
    metadata["experience_years"] = experience_or_seniority
    metadata.setdefault("seniority", experience_or_seniority)
    content["metadata"] = metadata
    return SimpleNamespace(id=jd.id, title=jd.title, content=json.dumps(content))


async def build_candidate_response(
    jd_id: int,
    page: int,
    per_page: int,
    db: Session,
    current_user: User,
    filter_skills: list[str] | None = None,
    filter_location: str | None = None,
    filter_seniority: str | None = None,
    all_candidates: bool = False,
):
    # 1. Fetch Job Description
    jd = visible_jd(db, current_user, jd_id)
    if not jd:
        raise HTTPException(status_code=404, detail="Job Description not found")

    # 2. Extract skills from JD Details or fallback to parsed content / title
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    skills = []
    location = None
    seniority = None
    experience_requirement = None
    
    if detail:
        if isinstance(detail.skills, list):
            skills = [s for s in detail.skills if s]
        if isinstance(detail.metadata_json, dict):
            location = detail.metadata_json.get("location")
            seniority = detail.metadata_json.get("seniority")
            experience_requirement = detail.metadata_json.get("experience_years") or detail.metadata_json.get("experience")

    if not skills or not location or not seniority:
        try:
            content_data = json.loads(jd.content) if jd.content else None
            if isinstance(content_data, dict):
                if not skills and "skills" in content_data:
                    skills = [s for s in content_data["skills"] if s]
                if "metadata" in content_data and isinstance(content_data["metadata"], dict):
                    metadata = content_data["metadata"]
                    location = location or metadata.get("location")
                    seniority = seniority or metadata.get("seniority")
                    experience_requirement = (
                        metadata.get("experience_years")
                        or metadata.get("experience")
                        or experience_requirement
                    )
                if not location and "location" in content_data:
                    location = content_data.get("location")
                if not seniority and "seniority" in content_data:
                    seniority = content_data.get("seniority")
        except Exception:
            pass

    if not skills and jd.title and not all_candidates:
        skills = [jd.title]

    if not skills and not all_candidates:
        raise HTTPException(
            status_code=400, 
            detail="Job Description lacks skills or title for Zoho criteria building"
        )

    # Recruiter-selected filters are applied before Zoho fetch and before LLM ranking.
    selected_skills = [skill for skill in (filter_skills or []) if str(skill).strip()]
    search_skills = [] if all_candidates else (selected_skills or skills)[:5]
    search_location = None if all_candidates else (filter_location or location)
    search_seniority = None if all_candidates else (filter_seniority or seniority)

    candidates = []
    search_strategy = "All candidates" if all_candidates else "Skills + location"
    search_notice = None

    if all_candidates:
        candidates = await ZohoRecruitService.fetch_candidates(
            skills=[],
            title=None,
            location=None,
            seniority=None,
            page=page,
            per_page=per_page,
            all_candidates=True,
        )
    else:
        # Query location-aware first, then broaden to skills-only if needed.
        # Experience/title are handled during ranking because the mock Zoho schema stores
        # years numerically and title as Current_Job_Title, not criteria-friendly fields.
        target_count = per_page
        attempts_used = []
        for attempt in filter_attempts(search_skills, search_location):
            attempt_candidates = await ZohoRecruitService.fetch_candidates(
                skills=attempt["skills"],
                title=jd.title,
                location=attempt["location"],
                seniority=attempt["seniority"],
                page=page,
                per_page=per_page,
            )
            attempts_used.append(attempt["label"])
            candidates = merge_candidates(candidates, attempt_candidates)
            if len(candidates) >= target_count:
                break

        search_strategy = attempts_used[-1] if attempts_used else search_strategy
        if len(attempts_used) > 1:
            search_notice = (
                "Location-aware filters returned too few candidates, so the search was broadened to skills before ranking. "
                "Experience and title are still considered during ranking."
            )

    ranking_jd = jd_for_ranking(jd, search_seniority)

    # 4. Rank candidates using LLM engine
    ranked_candidates = await CandidateRankingEngine.rank_candidates(
        candidates=candidates,
        jd=ranking_jd,
        jd_skills=skills
    )

    return {
        "jd_id": jd.id,
        "jd_title": jd.title,
        "search_skills": search_skills,
        "required_skills": skills,
        "search_location": search_location,
        "search_seniority": search_seniority,
        "experience_requirement": experience_requirement or seniority,
        "search_strategy": search_strategy,
        "search_notice": search_notice,
        "candidates": ranked_candidates,
        "total": len(ranked_candidates)
    }


@router.get("/candidates")
async def source_candidates(
    jd_id: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    skills: str | None = Query(None),
    location: str | None = Query(None),
    seniority: str | None = Query(None),
    all_candidates: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filter_skills = [skill.strip() for skill in (skills or "").split(",") if skill.strip()] or None
    return await build_candidate_response(jd_id, page, per_page, db, current_user, filter_skills, location, seniority, all_candidates)


@router.post("/candidates")
async def source_candidates_legacy(
    payload: SourcingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await build_candidate_response(
        payload.jd_id,
        payload.page,
        payload.per_page,
        db,
        current_user,
        payload.skills,
        payload.location,
        payload.seniority,
        payload.all_candidates,
    )
