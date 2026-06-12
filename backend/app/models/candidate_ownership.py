from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, func, text

from app.db.session import Base


class CandidateOwnership(Base):
    __tablename__ = "candidate_ownership"

    id = Column(Integer, primary_key=True, index=True)
    zoho_candidate_id = Column(String(100), nullable=False, index=True)
    candidate_name = Column(String(255), nullable=False)
    job_opening_id = Column(String(100), nullable=True, index=True)
    owner_recruiter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_recruiter_name = Column(String(255), nullable=False)
    sla_stage_id = Column(Integer, ForeignKey("sla_rules.id", ondelete="RESTRICT"), nullable=False)
    locked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="ACTIVE", index=True)

    __table_args__ = (
        Index(
            "ux_candidate_ownership_active_candidate",
            "zoho_candidate_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )


class SLARule(Base):
    __tablename__ = "sla_rules"

    id = Column(Integer, primary_key=True, index=True)
    blueprint = Column(String(40), nullable=False, default="SCR", index=True)
    stage_name = Column(String(120), unique=True, nullable=False)
    duration_days = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class OwnershipHistory(Base):
    __tablename__ = "ownership_history"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(100), nullable=False, index=True)
    action = Column(String(40), nullable=False, index=True)
    old_owner = Column(String(255), nullable=True)
    new_owner = Column(String(255), nullable=True)
    old_stage = Column(String(120), nullable=True)
    new_stage = Column(String(120), nullable=True)
    performed_by = Column(String(255), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
