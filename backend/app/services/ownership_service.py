from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.candidate_ownership import CandidateOwnership, OwnershipHistory, SLARule
from app.models.user import User


ACTIVE = "ACTIVE"
EXPIRED = "EXPIRED"
RELEASED = "RELEASED"
REASSIGNED = "REASSIGNED"

AUDIT_ACCEPTED = "Accepted"
AUDIT_RELEASED = "Released"
AUDIT_REASSIGNED = "Reassigned"
AUDIT_EXPIRED = "Expired"
AUDIT_STAGE_CHANGED = "Stage Changed"

DEFAULT_SLA_STAGES = [
    ("SCR", "Associated", 3),
    ("SCR", "Applied", 3),
    ("SCR", "Screen Select", 7),
    ("SCR", "Test/Asg Select", 7),
    ("R1/R2", "R1 Select", 7),
    ("R1/R2", "R2 Select", 7),
    ("T1/T2", "Tech ED1 Select", 7),
    ("T1/T2", "Tech ED2 Select", 7),
    ("CSCR", "Client Submission Done", 7),
    ("CSCR", "Client Test Select", 7),
    ("CR1", "CR1 Select", 7),
    ("CR2", "CR2 Select", 7),
    ("CR2", "CR3 Select", 7),
    ("OFR", "Final Select", 7),
    ("OFR", "Offer Approved", 7),
    ("OFR", "Offer Is Accepted", 90),
    ("JOIN", "Joined", 3650),
    ("REJ", "Reject", 7),
    ("REJ", "Rejected", 7),
    ("REJ", "Offer Drop", 7),
    ("ARC", "Archived", 7),
    ("ARC", "On Hold", 7),
]

LEGACY_SLA_STAGE_NAMES = {
    "Initial Screening",
    "Recruiter Submission",
    "Client Review",
    "Interview Coordination",
    "Offer Follow-up",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def ensure_sla_seed_data(db: Session) -> None:
    existing = {rule.stage_name for rule in db.query(SLARule).all()}
    changed = False
    for legacy_rule in db.query(SLARule).filter(SLARule.stage_name.in_(LEGACY_SLA_STAGE_NAMES)).all():
        if legacy_rule.active:
            legacy_rule.active = False
            changed = True
    for blueprint, stage_name, duration_days in DEFAULT_SLA_STAGES:
        if stage_name in existing:
            rule = db.query(SLARule).filter(SLARule.stage_name == stage_name).first()
            if rule and getattr(rule, "blueprint", None) != blueprint:
                rule.blueprint = blueprint
                changed = True
            continue
        db.add(SLARule(blueprint=blueprint, stage_name=stage_name, duration_days=duration_days, active=True))
        changed = True
    if changed:
        db.commit()


def stage_label(db: Session, stage_id: int | None) -> str | None:
    if not stage_id:
        return None
    rule = db.get(SLARule, stage_id)
    return rule.stage_name if rule else None


def active_stage_or_404(db: Session, stage_id: int) -> SLARule:
    rule = db.get(SLARule, stage_id)
    if not rule:
        raise HTTPException(status_code=404, detail="SLA stage not found")
    if not rule.active:
        raise HTTPException(status_code=422, detail="SLA stage is inactive")
    return rule


def active_ownership_query(db: Session, zoho_candidate_id: str):
    return db.query(CandidateOwnership).filter(
        CandidateOwnership.zoho_candidate_id == zoho_candidate_id,
        CandidateOwnership.status == ACTIVE,
    )


def get_current_active_ownership(db: Session, zoho_candidate_id: str) -> CandidateOwnership | None:
    ownership = active_ownership_query(db, zoho_candidate_id).first()
    if ownership and as_aware(ownership.expires_at) <= utcnow():
        mark_single_expired(db, ownership, "system")
        db.commit()
        return None
    return ownership


def mark_single_expired(db: Session, ownership: CandidateOwnership, performed_by: str) -> None:
    old_stage = stage_label(db, ownership.sla_stage_id)
    ownership.status = EXPIRED
    add_history(
        db,
        candidate_id=ownership.zoho_candidate_id,
        action=AUDIT_EXPIRED,
        old_owner=ownership.owner_recruiter_name,
        new_owner=None,
        old_stage=old_stage,
        new_stage=None,
        performed_by=performed_by,
    )


def expire_due_ownerships(db: Session, performed_by: str = "system") -> int:
    due = db.query(CandidateOwnership).filter(
        CandidateOwnership.status == ACTIVE,
        CandidateOwnership.expires_at <= utcnow(),
    ).all()
    for ownership in due:
        mark_single_expired(db, ownership, performed_by)
    if due:
        db.commit()
    return len(due)


def add_history(
    db: Session,
    *,
    candidate_id: str,
    action: str,
    old_owner: str | None,
    new_owner: str | None,
    old_stage: str | None,
    new_stage: str | None,
    performed_by: str,
) -> None:
    db.add(
        OwnershipHistory(
            candidate_id=candidate_id,
            action=action,
            old_owner=old_owner,
            new_owner=new_owner,
            old_stage=old_stage,
            new_stage=new_stage,
            performed_by=performed_by,
        )
    )


def accept_candidate(
    db: Session,
    *,
    zoho_candidate_id: str,
    candidate_name: str,
    job_opening_id: str | None,
    sla_stage_id: int,
    current_user: User,
) -> CandidateOwnership:
    stage = active_stage_or_404(db, sla_stage_id)
    now = utcnow()
    try:
        stale = active_ownership_query(db, zoho_candidate_id).filter(
            CandidateOwnership.expires_at <= now
        ).all()
        for ownership in stale:
            mark_single_expired(db, ownership, current_user.name)

        active = active_ownership_query(db, zoho_candidate_id).filter(
            CandidateOwnership.expires_at > now
        ).first()
        if active:
            raise HTTPException(status_code=409, detail=f"Candidate is owned by {active.owner_recruiter_name}")

        ownership = CandidateOwnership(
            zoho_candidate_id=zoho_candidate_id,
            candidate_name=candidate_name,
            job_opening_id=job_opening_id,
            owner_recruiter_id=current_user.id,
            owner_recruiter_name=current_user.name,
            sla_stage_id=stage.id,
            locked_at=now,
            expires_at=now + timedelta(days=stage.duration_days),
            status=ACTIVE,
        )
        db.add(ownership)
        add_history(
            db,
            candidate_id=zoho_candidate_id,
            action=AUDIT_ACCEPTED,
            old_owner=None,
            new_owner=current_user.name,
            old_stage=None,
            new_stage=stage.stage_name,
            performed_by=current_user.name,
        )
        db.commit()
        db.refresh(ownership)
        return ownership
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Candidate was accepted by another recruiter")


def change_stage(
    db: Session,
    *,
    zoho_candidate_id: str,
    sla_stage_id: int,
    current_user: User,
    is_admin: bool,
) -> CandidateOwnership:
    stage = active_stage_or_404(db, sla_stage_id)
    ownership = get_current_active_ownership(db, zoho_candidate_id)
    if not ownership:
        raise HTTPException(status_code=404, detail="No active ownership found")
    if ownership.owner_recruiter_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Only the owner or admin can change SLA stage")

    old_stage = stage_label(db, ownership.sla_stage_id)
    ownership.sla_stage_id = stage.id
    ownership.expires_at = utcnow() + timedelta(days=stage.duration_days)
    add_history(
        db,
        candidate_id=ownership.zoho_candidate_id,
        action=AUDIT_STAGE_CHANGED,
        old_owner=ownership.owner_recruiter_name,
        new_owner=ownership.owner_recruiter_name,
        old_stage=old_stage,
        new_stage=stage.stage_name,
        performed_by=current_user.name,
    )
    db.commit()
    db.refresh(ownership)
    return ownership


def release_candidate(db: Session, *, zoho_candidate_id: str, current_user: User, is_admin: bool) -> CandidateOwnership:
    ownership = get_current_active_ownership(db, zoho_candidate_id)
    if not ownership:
        raise HTTPException(status_code=404, detail="No active ownership found")
    if ownership.owner_recruiter_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Only the owner or admin can release ownership")

    old_stage = stage_label(db, ownership.sla_stage_id)
    ownership.status = RELEASED
    add_history(
        db,
        candidate_id=ownership.zoho_candidate_id,
        action=AUDIT_RELEASED,
        old_owner=ownership.owner_recruiter_name,
        new_owner=None,
        old_stage=old_stage,
        new_stage=None,
        performed_by=current_user.name,
    )
    db.commit()
    db.refresh(ownership)
    return ownership


def reassign_candidate(
    db: Session,
    *,
    zoho_candidate_id: str,
    new_owner: User,
    current_user: User,
) -> CandidateOwnership:
    ownership = get_current_active_ownership(db, zoho_candidate_id)
    if not ownership:
        raise HTTPException(status_code=404, detail="No active ownership found")

    old_owner = ownership.owner_recruiter_name
    old_stage = stage_label(db, ownership.sla_stage_id)
    ownership.status = REASSIGNED
    db.flush()
    replacement = CandidateOwnership(
        zoho_candidate_id=ownership.zoho_candidate_id,
        candidate_name=ownership.candidate_name,
        job_opening_id=ownership.job_opening_id,
        owner_recruiter_id=new_owner.id,
        owner_recruiter_name=new_owner.name,
        sla_stage_id=ownership.sla_stage_id,
        locked_at=utcnow(),
        expires_at=ownership.expires_at,
        status=ACTIVE,
    )
    db.add(replacement)
    add_history(
        db,
        candidate_id=ownership.zoho_candidate_id,
        action=AUDIT_REASSIGNED,
        old_owner=old_owner,
        new_owner=new_owner.name,
        old_stage=old_stage,
        new_stage=old_stage,
        performed_by=current_user.name,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Candidate ownership changed during reassignment")
    db.refresh(replacement)
    return replacement
