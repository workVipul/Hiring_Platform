from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class JDCreate(BaseModel):
    title: str
    content: Optional[str] = None
    ownership: str = "personal"
    jd_score: Optional[int] = Field(default=None, ge=0, le=100)
    pdf_url: Optional[str] = None
    context: Optional[str] = None
    skills: list[str] = []
    resume_skills: list[str] = []
    metadata: dict[str, Any] = {}


class JDGenerateRequest(BaseModel):
    raw_input: str
    input_type: str = "text"


class JDRefineRequest(BaseModel):
    instruction: str
    content: Optional[str] = None


class JDPublishRequest(BaseModel):
    ownership: str
    title: str
    content: str
    jd_score: Optional[int] = Field(default=None, ge=0, le=100)
    pdf_url: Optional[str] = None
    context: Optional[str] = None
    skills: list[str] = []
    resume_skills: list[str] = []
    metadata: dict[str, Any] = {}


class JDResponse(BaseModel):
    id: int
    title: str
    content: Optional[str]
    ownership: str
    jd_score: Optional[int]
    pdf_url: Optional[str]
    created_by: Optional[int]
    context: Optional[str] = None
    skills: list[str] = []
    resume_skills: list[str] = []
    metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JDListResponse(BaseModel):
    items: list[JDResponse]
    total: int


class GeneratedJD(BaseModel):
    title: str
    summary: str = ""
    responsibilities: list[str] = []
    requirements: list[str] = []
    nice_to_have: list[str] = []
    compensation: Any = ""
    about_company: Any = ""
    jd_score: Optional[int | float] = Field(default=None, ge=0, le=100)
    skills: list[str] = []
    resume_skills: list[str] = []
    metadata: dict[str, Any] = {}

    model_config = {"extra": "allow"}


def normalize_generated_jd(data: dict[str, Any]) -> dict[str, Any]:
    if "jd_score" in data and data["jd_score"] is not None:
        score = float(data["jd_score"])
        data["jd_score"] = round(score * 10 if score <= 10 else score)
    data.setdefault("skills", [])
    data.setdefault("resume_skills", [])
    data.setdefault("metadata", {})
    return GeneratedJD.model_validate(data).model_dump()
