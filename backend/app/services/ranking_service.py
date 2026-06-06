import logging
import json
import re
from app.llm.factory import get_llm_provider
from app.models.jd import JD
from app.core.config import settings

logger = logging.getLogger(__name__)

RANKING_SYSTEM = """You are an expert technical recruiter and candidate ranking specialist.
Rank candidates against the supplied JD intelligence. Return ONLY compact JSON, no markdown:
{"candidates":[{"id":"candidate id","skill_match_score":int,"experience_synergy":int,"fit_analysis":"one concise sentence","missing_skills":["skill"],"match_percentage":int}]}

Rules:
- Treat normalized and equivalent technologies as matches, such as Java/Spring Boot for Java development framework,
  AWS/Azure/GCP for cloud, CI/CD/Jenkins for DevOps, REST/RESTful API for REST APIs.
- skill_match_score is 0-100 based on matched must-have skills first, then preferred skills.
- experience_synergy is 0-100 based on candidate seniority or years against experience_min_years and experience_max_years.
- match_percentage = 0.60*skill_match_score + 0.25*experience_synergy + 0.15*soft/domain fit.
- Calibrate: 90+ exceptional, 70-89 strong, 50-69 possible, below 50 weak.
- Be concise and do not penalize candidates for wording differences when the technical meaning is equivalent."""

TECH_ALIASES = {
    "java development framework": {"java", "spring", "spring boot"},
    "java 8+": {"java"},
    "core java": {"java"},
    "golang": {"go", "golang"},
    "go lang": {"go", "golang"},
    "restful apis": {"rest", "api", "apis", "restful api"},
    "microservices architecture": {"microservices", "microservice"},
    "sql / nosql databases": {"sql", "nosql", "database", "databases"},
    "cloud development": {"cloud", "aws", "azure", "gcp"},
    "devops principles": {"devops", "ci/cd", "jenkins"},
}


def normalize_skill_tokens(skill: str) -> set[str]:
    value = re.sub(r"[^a-z0-9+#./ -]", " ", str(skill).lower())
    value = re.sub(r"\s+", " ", value).strip()
    tokens = {value} if value else set()
    tokens.update(part for part in re.split(r"[/,; ]+", value) if len(part) >= 2)
    for alias, expanded in TECH_ALIASES.items():
        if alias in value or value in expanded:
            tokens.update(expanded)
    return {token for token in tokens if token not in {"development", "framework", "principles", "practices", "strong", "knowledge"}}


def skill_matches(required: str, candidate_skills: list[str]) -> bool:
    required_tokens = normalize_skill_tokens(required)
    if not required_tokens:
        return False
    for candidate_skill in candidate_skills:
        candidate_tokens = normalize_skill_tokens(candidate_skill)
        if required_tokens & candidate_tokens:
            return True
        for req in required_tokens:
            for cand in candidate_tokens:
                if len(req) >= 3 and len(cand) >= 3:
                    # Prevent false positive match between Java and JavaScript
                    if {req, cand} == {"java", "javascript"}:
                        continue
                    if req in cand or cand in req:
                        return True
    return False


def as_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip(" -*\t") for item in re.split(r"[,;\n]", value) if item.strip(" -*\t")]
    return []


def extract_years(value: object) -> float | None:
    if value is None:
        return None
    match = re.search(r"\d+(\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def seniority_to_years(value: object) -> float | None:
    lowered = str(value or "").lower()
    if "intern" in lowered or "fresher" in lowered or "entry" in lowered:
        return 0
    if "junior" in lowered:
        return 1
    if "mid" in lowered:
        return 3
    if "senior" in lowered or "sr" in lowered:
        return 5
    if "lead" in lowered or "principal" in lowered or "architect" in lowered:
        return 8
    return extract_years(value)


def score_experience(candidate: dict, experience_min: float | None, experience_max: float | None, seniority: str | None = None) -> int:
    candidate_years = seniority_to_years(candidate.get("experience_level"))
    if candidate_years is None:
        return 72 if not experience_min else 62

    if experience_min is None and experience_max is None:
        target_years = seniority_to_years(seniority)
        if target_years is None:
            return 75
        return 90 if candidate_years >= target_years else max(45, int(90 - (target_years - candidate_years) * 12))

    minimum = experience_min or 0
    maximum = experience_max or max(minimum + 5, minimum)
    if minimum <= candidate_years <= maximum:
        return 94
    if candidate_years > maximum:
        return max(72, int(94 - min(22, (candidate_years - maximum) * 4)))
    return max(35, int(94 - (minimum - candidate_years) * 14))


def get_fallback_score(
    candidate: dict,
    jd_skills: list[str],
    experience_min: float | None = None,
    experience_max: float | None = None,
    seniority: str | None = None,
) -> dict:
    candidate_skills = candidate.get("skills", [])
    required_skills = [skill for skill in jd_skills if str(skill).strip()]

    matched = [skill for skill in required_skills if skill_matches(skill, candidate_skills)]
    missing = [skill for skill in required_skills if skill not in matched]
    skill_score = int(len(matched) / len(required_skills) * 100) if required_skills else 50
    experience_score = score_experience(candidate, experience_min, experience_max, seniority)

    missing_title = [str(skill).strip() for skill in missing][:5]
    overlap_display = ", ".join(str(skill) for skill in matched[:5]) if matched else "none"
    missing_display = ", ".join(missing_title) if missing_title else "none"
    
    return {
        "skill_match_score": skill_score,
        "experience_synergy": experience_score,
        "fit_analysis": f"Evaluated via keyword heuristics. Overlapping skills: {overlap_display}. Missing skills: {missing_display}.",
        "missing_skills": missing_title,
        "match_percentage": int(skill_score * 0.6 + experience_score * 0.25 + 70 * 0.15)
    }

class CandidateRankingEngine:
    @classmethod
    async def rank_candidates(cls, candidates: list[dict], jd: JD, jd_skills: list[str]) -> list[dict]:
        if not candidates:
            return []

        try:
            llm = get_llm_provider()
        except Exception as e:
            logger.error(f"Failed to load LLM provider, falling back to heuristics: {e}")
            llm = None

        # Parse JD content safely if it is JSON
        jd_text = jd.content or ""
        metadata = {}
        preferred_skills = []
        must_have_skills = []
        soft_skills = []
        try:
            parsed_jd = json.loads(jd_text)
            if isinstance(parsed_jd, dict):
                metadata = parsed_jd.get("metadata") if isinstance(parsed_jd.get("metadata"), dict) else {}
                preferred_skills = as_string_list(metadata.get("preferred_skills")) or as_string_list(parsed_jd.get("nice_to_have"))
                must_have_skills = as_string_list(metadata.get("must_have_skills")) or as_string_list(jd_skills)
                soft_skills = as_string_list(parsed_jd.get("soft_skills"))
                jd_text = (
                    f"Title: {parsed_jd.get('title')}\n"
                    f"Summary: {parsed_jd.get('summary')}\n"
                    f"Requirements: {parsed_jd.get('requirements')}\n"
                    f"Preferred: {parsed_jd.get('nice_to_have')}"
                )
        except Exception:
            pass

        experience_min = extract_years(metadata.get("experience_min_years"))
        experience_max = extract_years(metadata.get("experience_max_years"))
        seniority = metadata.get("seniority")
        if not must_have_skills:
            must_have_skills = jd_skills

        # 1. Pre-score all candidates with fast keyword heuristics
        for cand in candidates:
            cand["heuristic"] = get_fallback_score(cand, must_have_skills, experience_min, experience_max, seniority)

        # 2. Sort by heuristic match percentage descending
        candidates.sort(key=lambda x: x["heuristic"]["match_percentage"], reverse=True)

        # 3. Split into configurable top candidates for LLM scoring and remaining candidates.
        top_n = max(0, min(len(candidates), settings.SOURCING_LLM_RANK_LIMIT))
        to_llm = candidates[:top_n]
        remaining = candidates[top_n:]

        async def score_batch(batch: list[dict]) -> list[dict]:
            if not llm:
                return [{**cand, **cand["heuristic"]} for cand in batch]

            compact_candidates = [
                {
                    "id": cand["id"],
                    "current_title": (cand.get("raw_profile") or {}).get("Current_Job_Title"),
                    "skills": cand.get("skills", [])[:20],
                    "experience": cand.get("experience_level"),
                    "experience_years": (cand.get("raw_profile") or {}).get("Experience_in_Years"),
                    "location": cand.get("location"),
                }
                for cand in batch
            ]
            user_content = json.dumps(
                {
                    "jd": {
                        "title": jd.title,
                        "requirements": jd_text[:1800],
                        "must_have_skills": must_have_skills[:15],
                        "preferred_skills": preferred_skills[:10],
                        "soft_skills": soft_skills[:6],
                        "experience_min_years": experience_min,
                        "experience_max_years": experience_max,
                        "seniority": seniority,
                    },
                    "candidates": compact_candidates,
                },
                separators=(",", ":"),
            )
            try:
                result = await llm.complete_json(system=RANKING_SYSTEM, user=user_content, max_tokens=900)
                scored = result.get("candidates") if isinstance(result, dict) else []
                score_map = {str(item.get("id")): item for item in scored if isinstance(item, dict)}
                ranked = []
                for cand in batch:
                    score = score_map.get(str(cand["id"]), cand["heuristic"])
                    skill_match_score = max(
                        int(score.get("skill_match_score", cand["heuristic"]["skill_match_score"])),
                        int(cand["heuristic"]["skill_match_score"]),
                    )
                    experience_synergy = max(
                        int(score.get("experience_synergy", cand["heuristic"]["experience_synergy"])),
                        int(cand["heuristic"]["experience_synergy"]),
                    )
                    ranked.append({
                        **cand,
                        "skill_match_score": skill_match_score,
                        "experience_synergy": experience_synergy,
                        "fit_analysis": str(score.get("fit_analysis") or cand["heuristic"]["fit_analysis"]),
                        "missing_skills": list(score.get("missing_skills") or cand["heuristic"]["missing_skills"]),
                        "match_percentage": max(
                            int(score.get("match_percentage", cand["heuristic"]["match_percentage"])),
                            int(skill_match_score * 0.65 + experience_synergy * 0.35),
                        ),
                    })
                return ranked
            except Exception as e:
                logger.error(f"LLM batch ranking failed: {e}")
                return [{**cand, **cand["heuristic"]} for cand in batch]

        # 4. Score top candidates in one compact LLM call to reduce token and request cost.
        ranked_top = await score_batch(to_llm)

        # 5. Populate final fields for the remaining candidates using heuristic scores
        ranked_remaining = []
        for c in remaining:
            scores = c["heuristic"]
            c.pop("heuristic", None)
            ranked_remaining.append({**c, **scores})

        # Clean up heuristic temp keys from the top-N list
        for c in ranked_top:
            c.pop("heuristic", None)

        # 6. Combine, re-sort by final match percentage, and assign ranks
        ranked_all = ranked_top + ranked_remaining
        ranked_all.sort(key=lambda x: x.get("match_percentage", 0), reverse=True)

        for idx, cand in enumerate(ranked_all):
            cand["rank_position"] = idx + 1

        return ranked_all
