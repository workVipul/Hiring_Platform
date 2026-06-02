from dataclasses import dataclass, field
import re
from typing import Any

from app.services.ranking_service import skill_matches


@dataclass
class CandidateFilterSpec:
    must_have_skills: list[str] = field(default_factory=list)
    good_to_have_skills: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    experience_min_years: float | None = None
    experience_max_years: float | None = None
    notice_period: str | None = None
    current_company: str | None = None
    education: str | None = None
    employment_type: str | None = None
    visa_status: str | None = None
    availability: str | None = None
    relocation_preference: str | None = None


def deterministic_filter_candidates(candidates: list[dict], spec: CandidateFilterSpec) -> list[dict]:
    passed = []
    for candidate in candidates:
        verdict = evaluate_candidate(candidate, spec)
        if verdict["passed"]:
            candidate["deterministic_filter"] = verdict
            passed.append(candidate)
    return passed


def summarize_filter_rejections(candidates: list[dict], spec: CandidateFilterSpec) -> dict[str, int]:
    summary: dict[str, int] = {}
    for candidate in candidates:
        verdict = evaluate_candidate(candidate, spec)
        if verdict["passed"]:
            continue
        for reason in verdict["reasons"]:
            summary[reason] = summary.get(reason, 0) + 1
    return dict(sorted(summary.items(), key=lambda item: item[1], reverse=True))


def score_and_reduce_candidates(candidates: list[dict], spec: CandidateFilterSpec, limit: int) -> list[dict]:
    scored = []
    for candidate in candidates:
        score = deterministic_score(candidate, spec)
        candidate["pre_rank_score"] = score
        scored.append(candidate)
    scored.sort(key=lambda item: item.get("pre_rank_score", 0), reverse=True)
    return scored[:limit]


def evaluate_candidate(candidate: dict, spec: CandidateFilterSpec) -> dict[str, Any]:
    reasons = []
    raw = candidate.get("raw_profile") or {}
    candidate_skills = candidate.get("skills") or split_skill_set(raw.get("Skill_Set"))

    missing_must_have = [skill for skill in spec.must_have_skills if not skill_matches(skill, candidate_skills)]
    if missing_must_have:
        reasons.append(f"Missing mandatory skills: {', '.join(missing_must_have[:5])}")

    if spec.locations and not matches_any_location(candidate, raw, spec.locations):
        reasons.append("Location does not match JD or recruiter filter")

    candidate_years = extract_years(raw.get("Experience_in_Years") or candidate.get("experience_level"))
    if spec.experience_min_years is not None and (candidate_years is None or candidate_years < spec.experience_min_years):
        reasons.append("Below minimum experience")
    if spec.experience_max_years is not None and candidate_years is not None and candidate_years > spec.experience_max_years:
        reasons.append("Above maximum experience")

    hard_field_checks = [
        ("Notice_Period", spec.notice_period, "Notice period"),
        ("Current_Employer", spec.current_company, "Current company"),
        ("Highest_Qualification_Held", spec.education, "Education"),
        ("Employment_Type", spec.employment_type, "Employment type"),
        ("Visa_Status", spec.visa_status, "Visa status"),
        ("Candidate_Status", spec.availability, "Candidate availability"),
        ("Relocation_Preference", spec.relocation_preference, "Relocation preference"),
    ]
    for field_name, expected, label in hard_field_checks:
        if expected and not contains_text(raw.get(field_name), expected):
            reasons.append(f"{label} does not match")

    return {"passed": not reasons, "reasons": reasons}


def deterministic_score(candidate: dict, spec: CandidateFilterSpec) -> int:
    raw = candidate.get("raw_profile") or {}
    candidate_skills = candidate.get("skills") or split_skill_set(raw.get("Skill_Set"))
    good_matches = sum(1 for skill in spec.good_to_have_skills if skill_matches(skill, candidate_skills))
    good_score = int((good_matches / len(spec.good_to_have_skills)) * 30) if spec.good_to_have_skills else 15

    candidate_years = extract_years(raw.get("Experience_in_Years") or candidate.get("experience_level"))
    exp_score = 25
    if candidate_years is not None:
        if spec.experience_min_years is not None and candidate_years >= spec.experience_min_years:
            exp_score += 10
        if spec.experience_max_years is None or candidate_years <= spec.experience_max_years:
            exp_score += 5

    location_score = 15 if not spec.locations or matches_any_location(candidate, raw, spec.locations) else 0
    return min(100, 45 + good_score + exp_score + location_score)


def matches_any_location(candidate: dict, raw: dict, locations: list[str]) -> bool:
    candidate_terms = expand_location_terms([
        candidate.get("location"),
        raw.get("Location"),
        raw.get("City"),
        raw.get("State"),
        raw.get("Country"),
    ])
    expected_terms = expand_location_terms(locations)
    return bool(candidate_terms & expected_terms)


def contains_text(value: object, expected: str) -> bool:
    if value is None:
        return False
    return str(expected).strip().lower() in str(value).strip().lower()


def extract_years(value: object) -> float | None:
    if value is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def normalize_location_token(value: str) -> str:
    return str(value).split(",")[0].strip().lower()


def expand_location_terms(values: list[object]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        for term in split_location_value(value):
            terms.add(term)
            if term == "bangalore":
                terms.add("bengaluru")
            elif term == "bengaluru":
                terms.add("bangalore")
    return {term for term in terms if term}


def split_location_value(value: object) -> list[str]:
    if value is None:
        return []
    return [
        part.strip().lower()
        for part in re.split(r"\bor\b|[,|;/]", str(value), flags=re.IGNORECASE)
        if part.strip()
    ]


def split_skill_set(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[,;\n]", str(value)) if part.strip()]
