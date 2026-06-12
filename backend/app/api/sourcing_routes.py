import json
from datetime import timezone
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.security import get_access_type, get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.jd import JD
from app.models.jd_detail import JDDetail
from app.models.candidate_ownership import CandidateOwnership, SLARule
from app.models.user import User
from app.services.ownership_service import expire_due_ownerships, utcnow
from app.services.zoho_service import ZohoRecruitService
from app.services.ranking_service import CandidateRankingEngine
from app.services.candidate_filtering import (
    CandidateFilterSpec,
    deterministic_filter_candidates,
    summarize_filter_rejections,
    score_and_reduce_candidates,
)

router = APIRouter(prefix="/api/v1/sourcing", tags=["Sourcing"])

class SourcingRequest(BaseModel):
    jd_id: int
    page: int = 1
    per_page: int = 20
    skills: list[str] | None = None
    location: str | None = None
    seniority: str | None = None
    all_candidates: bool = False
    notice_period: str | None = None
    current_company: str | None = None
    education: str | None = None
    employment_type: str | None = None
    visa_status: str | None = None
    availability: str | None = None
    relocation_preference: str | None = None
    recency: str | None = None
    good_skills: list[str] | None = None

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


def list_from_unknown(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def unique_keep_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value).strip()
        key = text.lower()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def combine_locations(*values: str | None) -> list[str]:
    locations = []
    for value in values:
        if not value:
            continue
        import re
        locations.extend([part.strip() for part in re.split(r"\bor\b|[,|;/]", str(value), flags=re.IGNORECASE) if part.strip()])
    return unique_keep_order(locations)


def merge_ownership_data(db: Session, current_user: User, candidates: list[dict]) -> list[dict]:
    if not candidates:
        return candidates

    expire_due_ownerships(db)
    candidate_ids = [str(candidate.get("id")) for candidate in candidates if candidate.get("id")]
    if not candidate_ids:
        return candidates

    ownerships = db.query(CandidateOwnership, SLARule).join(
        SLARule, CandidateOwnership.sla_stage_id == SLARule.id
    ).filter(
        CandidateOwnership.zoho_candidate_id.in_(candidate_ids),
        CandidateOwnership.status == "ACTIVE",
        CandidateOwnership.expires_at > utcnow(),
    ).all()
    ownership_by_candidate = {
        ownership.zoho_candidate_id: (ownership, rule)
        for ownership, rule in ownerships
    }

    enriched = []
    for candidate in candidates:
        candidate_id = str(candidate.get("id"))
        ownership_tuple = ownership_by_candidate.get(candidate_id)
        if not ownership_tuple:
            enriched.append({**candidate, "ownership": None})
            continue

        ownership, rule = ownership_tuple
        expires_at = ownership.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        remaining_seconds = max(0, int((expires_at - utcnow()).total_seconds()))
        enriched.append(
            {
                **candidate,
                "ownership": {
                    "id": ownership.id,
                    "zoho_candidate_id": ownership.zoho_candidate_id,
                    "candidate_name": ownership.candidate_name,
                    "job_opening_id": ownership.job_opening_id,
                    "owner_recruiter_id": ownership.owner_recruiter_id,
                    "owner_recruiter_name": ownership.owner_recruiter_name,
                    "sla_stage_id": ownership.sla_stage_id,
                    "sla_stage_name": rule.stage_name,
                    "locked_at": ownership.locked_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "status": ownership.status,
                    "remaining_seconds": remaining_seconds,
                    "is_locked_by_other": ownership.owner_recruiter_id != current_user.id and remaining_seconds > 0,
                },
            }
        )
    return enriched


def number_from_unknown(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        import re
        match = re.search(r"\d+(?:\.\d+)?", value)
        return float(match.group(0)) if match else None
    return None


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
    notice_period: str | None = None,
    current_company: str | None = None,
    education: str | None = None,
    employment_type: str | None = None,
    visa_status: str | None = None,
    availability: str | None = None,
    relocation_preference: str | None = None,
    recency: str | None = None,
    filter_good_skills: list[str] | None = None,
):
    # 1. Fetch Job Description
    jd = visible_jd(db, current_user, jd_id)
    if not jd:
        raise HTTPException(status_code=404, detail="Job Description not found")

    # 2. Extract skills from JD Details or fallback to parsed content / title
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    skills = []
    must_have_skills = []
    good_to_have_skills = []
    location = None
    seniority = None
    experience_requirement = None
    experience_min_years = None
    experience_max_years = None
    
    if detail:
        if isinstance(detail.skills, list):
            skills = [s for s in detail.skills if s]
        if isinstance(detail.metadata_json, dict):
            must_have_skills = list_from_unknown(detail.metadata_json.get("must_have_skills"))
            good_to_have_skills = list_from_unknown(detail.metadata_json.get("preferred_skills"))
            location = detail.metadata_json.get("location")
            seniority = detail.metadata_json.get("seniority")
            experience_requirement = detail.metadata_json.get("experience_years") or detail.metadata_json.get("experience")
            experience_min_years = number_from_unknown(detail.metadata_json.get("experience_min_years"))
            experience_max_years = number_from_unknown(detail.metadata_json.get("experience_max_years"))

    if not skills or not location or not seniority:
        try:
            content_data = json.loads(jd.content) if jd.content else None
            if isinstance(content_data, dict):
                if not skills and "skills" in content_data:
                    skills = [s for s in content_data["skills"] if s]
                if "metadata" in content_data and isinstance(content_data["metadata"], dict):
                    metadata = content_data["metadata"]
                    must_have_skills = must_have_skills or list_from_unknown(metadata.get("must_have_skills"))
                    good_to_have_skills = good_to_have_skills or list_from_unknown(metadata.get("preferred_skills"))
                    location = location or metadata.get("location")
                    seniority = seniority or metadata.get("seniority")
                    experience_requirement = (
                        metadata.get("experience_years")
                        or metadata.get("experience")
                        or experience_requirement
                    )
                    experience_min_years = experience_min_years or number_from_unknown(metadata.get("experience_min_years"))
                    experience_max_years = experience_max_years or number_from_unknown(metadata.get("experience_max_years"))
                if not location and "location" in content_data:
                    location = content_data.get("location")
                if not seniority and "seniority" in content_data:
                    seniority = content_data.get("seniority")
                if not good_to_have_skills:
                    good_to_have_skills = list_from_unknown(content_data.get("nice_to_have"))
        except Exception:
            pass

    must_have_skills = unique_keep_order(must_have_skills or skills)
    good_to_have_skills = unique_keep_order(good_to_have_skills)

    if not skills and jd.title and not all_candidates:
        skills = [jd.title]
    if not must_have_skills and skills:
        must_have_skills = unique_keep_order(skills)

    if not must_have_skills and not all_candidates:
        raise HTTPException(
            status_code=400, 
            detail="Job Description lacks skills or title for Zoho criteria building"
        )

    # Recruiter-selected filters are applied before Zoho fetch and before LLM ranking.
    # Selected skills are treated as must-have gates. JD location and recruiter location
    # are combined with OR semantics inside the Zoho criteria.
    selected_skills = [skill for skill in (filter_skills or []) if str(skill).strip()]
    search_must_have_skills = [] if all_candidates else unique_keep_order(selected_skills or must_have_skills)[:8]
    
    if all_candidates:
        search_good_to_have_skills = []
    else:
        if filter_good_skills is not None:
            search_good_to_have_skills = [skill for skill in good_to_have_skills if skill in filter_good_skills]
        else:
            search_good_to_have_skills = good_to_have_skills
        search_good_to_have_skills = unique_keep_order(search_good_to_have_skills)[:8]
        search_good_to_have_skills = [skill for skill in search_good_to_have_skills if skill.lower() not in {s.lower() for s in search_must_have_skills}]

    search_locations = [] if all_candidates else combine_locations(location, filter_location)
    search_location = " OR ".join(search_locations) if search_locations else None
    search_seniority = None if all_candidates else (filter_seniority or seniority)

    recency_months = None
    if recency == "3_months":
        recency_months = 3
    elif recency == "6_months":
        recency_months = 6

    filter_spec = CandidateFilterSpec(
        must_have_skills=search_must_have_skills,
        good_to_have_skills=search_good_to_have_skills,
        locations=search_locations,
        experience_min_years=experience_min_years,
        experience_max_years=experience_max_years,
        notice_period=notice_period,
        current_company=current_company,
        education=education,
        employment_type=employment_type,
        visa_status=visa_status,
        availability=availability,
        relocation_preference=relocation_preference,
        recency_months=recency_months,
    )

    candidates = []
    search_strategy = "All candidates" if all_candidates else "Zoho API hard-filtered retrieval"
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
        for zoho_page in range(page, page + settings.SOURCING_MAX_ZOHO_PAGES):
            page_candidates = await ZohoRecruitService.fetch_candidates(
                must_have_skills=search_must_have_skills,
                good_to_have_skills=search_good_to_have_skills,
                title=jd.title,
                location=search_locations,
                seniority=search_seniority,
                experience_min_years=experience_min_years,
                experience_max_years=experience_max_years,
                notice_period=notice_period,
                current_company=current_company,
                education=education,
                employment_type=employment_type,
                visa_status=visa_status,
                availability=availability,
                relocation_preference=relocation_preference,
                page=zoho_page,
                per_page=settings.SOURCING_ZOHO_PAGE_SIZE,
            )
            candidates = merge_candidates(candidates, page_candidates)
            if len(page_candidates) < settings.SOURCING_ZOHO_PAGE_SIZE or len(candidates) >= settings.SOURCING_SCORING_LIMIT:
                break

        search_notice = (
            "Zoho search query is filtered with AND across must-have skills and OR across selected city values. "
            "City matching uses the City field only; state/country are not used for city pre-filtering. "
            "Experience and supported recruiter hard filters are included in the Zoho criteria when provided."
        )

    retrieved_count = len(candidates)
    filtered_candidates = deterministic_filter_candidates(candidates, filter_spec) if not all_candidates else candidates
    filter_rejections = summarize_filter_rejections(candidates, filter_spec) if not all_candidates else {}
    deterministic_count = len(filtered_candidates)
    reduced_candidates = score_and_reduce_candidates(
        filtered_candidates,
        filter_spec,
        settings.SOURCING_SCORING_LIMIT,
    )

    ranking_jd = jd_for_ranking(jd, experience_requirement)

    # 4. Rank reduced candidates using LLM engine.
    ranked_candidates = await CandidateRankingEngine.rank_candidates(
        candidates=reduced_candidates,
        jd=ranking_jd,
        jd_skills=search_must_have_skills or skills
    )
    from app.services.zoho_service import build_criteria
    zoho_criteria = "" if all_candidates else build_criteria(
        must_have_skills=search_must_have_skills,
        good_to_have_skills=search_good_to_have_skills,
        location=search_locations,
        seniority=search_seniority,
        experience_min_years=experience_min_years,
        experience_max_years=experience_max_years,
        notice_period=notice_period,
        current_company=current_company,
        education=education,
        employment_type=employment_type,
        visa_status=visa_status,
        availability=availability,
        relocation_preference=relocation_preference,
    )
    result_limit = min(per_page, settings.SOURCING_RESULT_LIMIT)
    ranked_candidates = ranked_candidates[:result_limit]
    ranked_candidates = merge_ownership_data(db, current_user, ranked_candidates)

    return {
        "jd_id": jd.id,
        "jd_title": jd.title,
        "search_skills": search_must_have_skills,
        "required_skills": search_must_have_skills,
        "good_to_have_skills": search_good_to_have_skills,
        "search_location": search_location,
        "search_seniority": search_seniority,
        "experience_requirement": experience_requirement,
        "search_strategy": search_strategy,
        "search_notice": search_notice,
        "zoho_criteria": zoho_criteria,
        "pipeline_counts": {
            "retrieved_from_zoho": retrieved_count,
            "deterministic_filtered": deterministic_count,
            "sent_to_scoring": len(reduced_candidates),
            "sent_to_llm": min(len(reduced_candidates), settings.SOURCING_LLM_RANK_LIMIT),
            "returned": len(ranked_candidates),
        },
        "filter_rejections": filter_rejections,
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
    notice_period: str | None = Query(None),
    current_company: str | None = Query(None),
    education: str | None = Query(None),
    employment_type: str | None = Query(None),
    visa_status: str | None = Query(None),
    availability: str | None = Query(None),
    relocation_preference: str | None = Query(None),
    recency: str | None = Query(None),
    good_skills: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filter_skills = [skill.strip() for skill in (skills or "").split(",") if skill.strip()] or None
    filter_good_skills = [skill.strip() for skill in (good_skills or "").split(",") if skill.strip()] or None
    return await build_candidate_response(
        jd_id,
        page,
        per_page,
        db,
        current_user,
        filter_skills,
        location,
        seniority,
        all_candidates,
        notice_period,
        current_company,
        education,
        employment_type,
        visa_status,
        availability,
        relocation_preference,
        recency,
        filter_good_skills,
    )


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
        payload.notice_period,
        payload.current_company,
        payload.education,
        payload.employment_type,
        payload.visa_status,
        payload.availability,
        payload.relocation_preference,
        payload.recency,
        payload.good_skills,
    )
