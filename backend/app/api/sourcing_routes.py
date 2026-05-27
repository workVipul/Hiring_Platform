import json
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

    # 3. Query candidates from Zoho Recruit with AND criteria across title, skills, location, and seniority.
    candidates = await ZohoRecruitService.fetch_candidates(
        skills=search_skills,
        title=jd.title,
        location=search_location,
        seniority=search_seniority,
        page=page,
        per_page=per_page,
        all_candidates=all_candidates,
    )

    # 4. Rank candidates using LLM engine
    ranked_candidates = await CandidateRankingEngine.rank_candidates(
        candidates=candidates,
        jd=jd,
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
