from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_access_type, get_current_user
from app.db.session import get_db
from app.models.candidate_ownership import CandidateOwnership, OwnershipHistory, SLARule
from app.models.user import User
from app.schemas.ownership import (
    OwnershipAcceptRequest,
    OwnershipHistoryResponse,
    OwnershipReassignRequest,
    OwnershipResponse,
    OwnershipStageUpdateRequest,
    RecruiterResponse,
    SLARuleCreate,
    SLARuleResponse,
    SLARuleUpdate,
)
from app.services.ownership_service import (
    accept_candidate,
    change_stage,
    ensure_sla_seed_data,
    expire_due_ownerships,
    get_current_active_ownership,
    reassign_candidate,
    release_candidate,
    stage_label,
    utcnow,
)


router = APIRouter(prefix="/api/v1/ownership", tags=["Candidate Ownership"])


def is_admin_or_manager(user: User, db: Session) -> bool:
    return get_access_type(user, db) in {"admin", "manager"}


def require_admin_or_manager(user: User, db: Session) -> None:
    if not is_admin_or_manager(user, db):
        raise HTTPException(status_code=403, detail="Admin or manager access required")


def serialize_ownership(db: Session, ownership: CandidateOwnership, current_user: User) -> OwnershipResponse:
    now = utcnow()
    expires_at = ownership.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    remaining_seconds = max(0, int((expires_at - now).total_seconds()))
    return OwnershipResponse(
        id=ownership.id,
        zoho_candidate_id=ownership.zoho_candidate_id,
        candidate_name=ownership.candidate_name,
        job_opening_id=ownership.job_opening_id,
        owner_recruiter_id=ownership.owner_recruiter_id,
        owner_recruiter_name=ownership.owner_recruiter_name,
        sla_stage_id=ownership.sla_stage_id,
        sla_stage_name=stage_label(db, ownership.sla_stage_id),
        locked_at=ownership.locked_at,
        expires_at=ownership.expires_at,
        status=ownership.status,
        remaining_seconds=remaining_seconds,
        is_locked_by_other=ownership.owner_recruiter_id != current_user.id and remaining_seconds > 0,
    )


@router.get("/sla-rules", response_model=list[SLARuleResponse])
def list_sla_rules(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_sla_seed_data(db)
    query = db.query(SLARule)
    if active_only:
        query = query.filter(SLARule.active.is_(True))
    return query.order_by(SLARule.active.desc(), SLARule.stage_name.asc()).all()


@router.post("/sla-rules", response_model=SLARuleResponse, status_code=201)
def create_sla_rule(
    payload: SLARuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin_or_manager(current_user, db)
    rule = SLARule(
        blueprint=payload.blueprint.strip().upper(),
        stage_name=payload.stage_name.strip(),
        duration_days=payload.duration_days,
        active=payload.active,
    )
    db.add(rule)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="SLA stage name already exists") from exc
    db.refresh(rule)
    return rule


@router.put("/sla-rules/{rule_id}", response_model=SLARuleResponse)
def update_sla_rule(
    rule_id: int,
    payload: SLARuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin_or_manager(current_user, db)
    rule = db.get(SLARule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="SLA rule not found")
    if payload.stage_name is not None:
        rule.stage_name = payload.stage_name.strip()
    if payload.blueprint is not None:
        rule.blueprint = payload.blueprint.strip().upper()
    if payload.duration_days is not None:
        rule.duration_days = payload.duration_days
    if payload.active is not None:
        rule.active = payload.active
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="SLA stage name already exists") from exc
    db.refresh(rule)
    return rule


@router.get("/recruiters", response_model=list[RecruiterResponse])
def list_recruiters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin_or_manager(current_user, db)
    return db.query(User).order_by(User.name.asc()).all()


@router.get("/active", response_model=list[OwnershipResponse])
def list_active_ownerships(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin_or_manager(current_user, db)
    expire_due_ownerships(db)
    records = db.query(CandidateOwnership).filter(CandidateOwnership.status == "ACTIVE").order_by(CandidateOwnership.expires_at.asc()).all()
    return [serialize_ownership(db, record, current_user) for record in records]


@router.get("/mine", response_model=list[OwnershipResponse])
def list_my_ownerships(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expire_due_ownerships(db)
    records = db.query(CandidateOwnership).filter(
        CandidateOwnership.status == "ACTIVE",
        CandidateOwnership.owner_recruiter_id == current_user.id,
    ).order_by(CandidateOwnership.expires_at.asc()).all()
    return [serialize_ownership(db, record, current_user) for record in records]


@router.post("/accept", response_model=OwnershipResponse, status_code=201)
def accept_ownership(
    payload: OwnershipAcceptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ownership = accept_candidate(
        db,
        zoho_candidate_id=payload.zoho_candidate_id,
        candidate_name=payload.candidate_name,
        job_opening_id=payload.job_opening_id,
        sla_stage_id=payload.sla_stage_id,
        current_user=current_user,
    )
    return serialize_ownership(db, ownership, current_user)


@router.get("/{zoho_candidate_id}", response_model=OwnershipResponse | None)
def get_ownership(
    zoho_candidate_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ownership = get_current_active_ownership(db, zoho_candidate_id)
    return serialize_ownership(db, ownership, current_user) if ownership else None


@router.patch("/{zoho_candidate_id}/stage", response_model=OwnershipResponse)
def update_ownership_stage(
    zoho_candidate_id: str,
    payload: OwnershipStageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ownership = change_stage(
        db,
        zoho_candidate_id=zoho_candidate_id,
        sla_stage_id=payload.sla_stage_id,
        current_user=current_user,
        is_admin=is_admin_or_manager(current_user, db),
    )
    return serialize_ownership(db, ownership, current_user)


@router.post("/{zoho_candidate_id}/release", response_model=OwnershipResponse)
def release_ownership(
    zoho_candidate_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ownership = release_candidate(
        db,
        zoho_candidate_id=zoho_candidate_id,
        current_user=current_user,
        is_admin=is_admin_or_manager(current_user, db),
    )
    return serialize_ownership(db, ownership, current_user)


@router.post("/{zoho_candidate_id}/reassign", response_model=OwnershipResponse)
def reassign_ownership(
    zoho_candidate_id: str,
    payload: OwnershipReassignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin_or_manager(current_user, db)
    new_owner = db.get(User, payload.new_owner_recruiter_id)
    if not new_owner:
        raise HTTPException(status_code=404, detail="Recruiter not found")
    ownership = reassign_candidate(db, zoho_candidate_id=zoho_candidate_id, new_owner=new_owner, current_user=current_user)
    return serialize_ownership(db, ownership, current_user)


@router.get("/{zoho_candidate_id}/history", response_model=list[OwnershipHistoryResponse])
def ownership_history(
    zoho_candidate_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active = get_current_active_ownership(db, zoho_candidate_id)
    if active and active.owner_recruiter_id != current_user.id and not is_admin_or_manager(current_user, db):
        raise HTTPException(status_code=403, detail="Only the owner or admin can view ownership history")
    return db.query(OwnershipHistory).filter(
        OwnershipHistory.candidate_id == zoho_candidate_id
    ).order_by(OwnershipHistory.timestamp.desc()).all()
