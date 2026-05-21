import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.models.jd import JD
from app.models.jd_detail import JDDetail
from app.services.zoho_service import ZohoRecruitService
from app.services.ranking_service import CandidateRankingEngine

router = APIRouter(prefix="/api/v1/sourcing", tags=["Sourcing"])

class SourcingRequest(BaseModel):
    jd_id: int
    page: int = 1
    per_page: int = 20

@router.post("/candidates")
async def source_candidates(payload: SourcingRequest, db: Session = Depends(get_db)):
    # 1. Fetch Job Description
    jd = db.query(JD).filter(JD.id == payload.jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="Job Description not found")

    # 2. Extract skills from JD Details or fallback to parsed content / title
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    skills = []
    location = None
    seniority = None
    
    if detail:
        if isinstance(detail.skills, list):
            skills = [s for s in detail.skills if s]
        if isinstance(detail.metadata_json, dict):
            location = detail.metadata_json.get("location")
            seniority = detail.metadata_json.get("seniority")

    if not skills or not location or not seniority:
        try:
            content_data = json.loads(jd.content) if jd.content else None
            if isinstance(content_data, dict):
                if not skills and "skills" in content_data:
                    skills = [s for s in content_data["skills"] if s]
                if not location:
                    if "metadata" in content_data and isinstance(content_data["metadata"], dict):
                        location = content_data["metadata"].get("location")
                        seniority = content_data["metadata"].get("seniority")
                    if not location and "location" in content_data:
                        location = content_data.get("location")
                    if not seniority and "seniority" in content_data:
                        seniority = content_data.get("seniority")
        except Exception:
            pass

    if not skills and jd.title:
        skills = [jd.title]

    if not skills:
        raise HTTPException(
            status_code=400, 
            detail="Job Description lacks skills or title for Zoho criteria building"
        )

    # Limit maximum skills used for search criteria to prevent overly long Zoho queries
    search_skills = skills[:5]

    # 3. Query candidates from Zoho Recruit demo portal with skills, title, location, and seniority
    candidates = await ZohoRecruitService.fetch_candidates(
        skills=search_skills,
        title=jd.title,
        location=location,
        seniority=seniority,
        page=payload.page,
        per_page=payload.per_page
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
        "candidates": ranked_candidates,
        "total": len(ranked_candidates)
    }
