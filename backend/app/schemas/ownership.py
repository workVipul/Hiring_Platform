from datetime import datetime

from pydantic import BaseModel, Field


class SLARuleCreate(BaseModel):
    blueprint: str = Field(default="SCR", min_length=1, max_length=40)
    stage_name: str = Field(min_length=2, max_length=120)
    duration_days: int = Field(ge=0, le=3650)
    active: bool = True


class SLARuleUpdate(BaseModel):
    blueprint: str | None = Field(default=None, min_length=1, max_length=40)
    stage_name: str | None = Field(default=None, min_length=2, max_length=120)
    duration_days: int | None = Field(default=None, ge=0, le=3650)
    active: bool | None = None


class SLARuleResponse(BaseModel):
    id: int
    blueprint: str
    stage_name: str
    duration_days: int
    active: bool

    model_config = {"from_attributes": True}


class OwnershipAcceptRequest(BaseModel):
    zoho_candidate_id: str = Field(min_length=1, max_length=100)
    candidate_name: str = Field(min_length=1, max_length=255)
    job_opening_id: str | None = Field(default=None, max_length=100)
    sla_stage_id: int


class OwnershipStageUpdateRequest(BaseModel):
    sla_stage_id: int


class OwnershipReassignRequest(BaseModel):
    new_owner_recruiter_id: int


class OwnershipResponse(BaseModel):
    id: int
    zoho_candidate_id: str
    candidate_name: str
    job_opening_id: str | None
    owner_recruiter_id: int | None
    owner_recruiter_name: str
    sla_stage_id: int
    sla_stage_name: str | None
    locked_at: datetime
    expires_at: datetime
    status: str
    remaining_seconds: int
    is_locked_by_other: bool


class OwnershipHistoryResponse(BaseModel):
    id: int
    candidate_id: str
    action: str
    old_owner: str | None
    new_owner: str | None
    old_stage: str | None
    new_stage: str | None
    performed_by: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class RecruiterResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = {"from_attributes": True}
