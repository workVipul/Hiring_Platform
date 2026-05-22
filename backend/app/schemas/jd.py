from datetime import datetime
import re
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
    created_by_name: Optional[str] = None
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
    page: int = 1
    per_page: int = 12


class GeneratedJD(BaseModel):
    title: str
    summary: str = ""
    responsibilities: list[str] = []
    requirements: list[str] = []
    nice_to_have: list[str] = []
    soft_skills: list[str] = []
    compensation: Any = ""
    about_company: Any = ""
    jd_score: Optional[int | float] = Field(default=None, ge=0, le=100)
    skills: list[str] = []
    resume_skills: list[str] = []
    metadata: dict[str, Any] = {}

    model_config = {"extra": "allow"}


def normalize_generated_jd(data: dict[str, Any]) -> dict[str, Any]:
    data["jd_score"] = None
    list_fields = ("responsibilities", "requirements", "nice_to_have", "soft_skills", "skills", "resume_skills")
    for key in list_fields:
        value = data.get(key)
        if isinstance(value, str):
            data[key] = [item.strip(" -*\t") for item in value.splitlines() if item.strip()]
        elif value is None:
            data[key] = []

    data.setdefault("skills", [])
    data.setdefault("resume_skills", [])
    if not isinstance(data.get("metadata"), dict):
        data["metadata"] = {}

    data["metadata"] = normalize_metadata(data["metadata"])
    data = normalize_jd_sections(data)
    normalized = GeneratedJD.model_validate(data).model_dump()
    normalized["jd_score"] = calculate_jd_quality_score(normalized)
    return normalized


def normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    for key in ("experience_years", "experience"):
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            metadata[key] = f"{value:g} years"
        elif isinstance(value, str) and re.fullmatch(r"\d+(\.\d+)?\+?", value.strip()):
            metadata[key] = f"{value.strip()} years"
    return metadata


def normalize_jd_sections(data: dict[str, Any]) -> dict[str, Any]:
    skills = unique_keep_order([str(skill).strip() for skill in data.get("skills") or [] if is_technical_skill(str(skill))])
    skill_keys = {skill.lower() for skill in skills}
    requirements = []
    soft_skills = list(data.get("soft_skills") or [])

    for item in data.get("requirements") or []:
        text = str(item).strip()
        if not text or text.lower() in skill_keys:
            continue
        if is_experience_only_requirement(text):
            continue
        if is_soft_skill_requirement(text):
            if text not in soft_skills:
                soft_skills.append(text)
            continue
        if is_work_mode_requirement(text):
            continue
        requirements.append(clean_requirement_text(text))

    if not requirements and skills:
        requirements = [f"Strong expertise in {skill}" for skill in skills[:8]]

    data["requirements"] = unique_keep_order(requirements)
    data["soft_skills"] = unique_keep_order([str(skill).strip() for skill in soft_skills if str(skill).strip()])
    data["skills"] = skills
    return data


def is_experience_only_requirement(text: str) -> bool:
    lowered = text.lower()
    has_years = bool(re.search(r"\b\d+\+?\s*(years?|yrs?)\b", lowered))
    technical_terms = (
        "spring", "java", "go", "golang", "microservice", "api", "sql", "cloud",
        "docker", "kubernetes", "aws", "azure", "gcp", "kafka", "hibernate", "jpa",
    )
    return has_years and not any(token in lowered for token in technical_terms)


def is_soft_skill_requirement(text: str) -> bool:
    lowered = text.lower()
    soft_terms = (
        "communication", "collaboration", "leadership", "team management", "problem-solving",
        "problem solving", "analytical", "stakeholder", "mentor", "hybrid environment",
    )
    return any(term in lowered for term in soft_terms)


def is_work_mode_requirement(text: str) -> bool:
    lowered = text.lower()
    return "hybrid environment" in lowered or "remote environment" in lowered or "onsite environment" in lowered


def is_technical_skill(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    blocked = ("excellent", "communication", "collaboration", "leadership", "problem", "hybrid", "agile development methodology")
    return not any(term in lowered for term in blocked)


def clean_requirement_text(text: str) -> str:
    return re.sub(
        r"^\d+\+?\s*(years?|yrs?)\s+of\s+experience\s+in\s+",
        "Experience with ",
        text,
        flags=re.IGNORECASE,
    ).strip()


def unique_keep_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def calculate_jd_quality_score(data: dict[str, Any]) -> int:
    """Score JD completeness from stored content instead of trusting LLM output."""
    score = 0

    title = str(data.get("title") or "").strip()
    summary = str(data.get("summary") or "").strip()
    responsibilities = [x for x in data.get("responsibilities") or [] if str(x).strip()]
    requirements = [x for x in data.get("requirements") or [] if str(x).strip()]
    nice_to_have = [x for x in data.get("nice_to_have") or [] if str(x).strip()]
    skills = [x for x in data.get("skills") or [] if str(x).strip()]
    resume_skills = [x for x in data.get("resume_skills") or [] if str(x).strip()]
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    if len(title) >= 5:
        score += 10
    if len(summary) >= 120:
        score += 15
    elif len(summary) >= 50:
        score += 8

    score += min(15, len(responsibilities) * 3)
    score += min(18, len(requirements) * 3)
    score += min(12, len(skills) * 2)
    score += min(8, len(resume_skills) * 2)
    score += min(6, len(nice_to_have) * 2)

    metadata_keys = {str(key).lower() for key in metadata}
    if {"experience_years", "experience", "seniority"} & metadata_keys:
        score += 8
    if {"location", "work_mode", "department"} & metadata_keys:
        score += 5
    if isinstance(metadata.get("skill_weights"), dict) and metadata["skill_weights"]:
        score += 3

    return max(0, min(100, score))
