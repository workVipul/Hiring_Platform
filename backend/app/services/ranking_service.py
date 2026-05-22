import logging
import json
import re
from app.llm.factory import get_llm_provider
from app.models.jd import JD

logger = logging.getLogger(__name__)

RANKING_SYSTEM = """You are an expert technical recruiter.
Score candidate fit against the JD. Return compact JSON only:
{"candidates":[{"id":"candidate id","skill_match_score":int,"experience_synergy":int,"fit_analysis":"one concise sentence","missing_skills":["skill"],"match_percentage":int}]}"""

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
        if any(req in cand or cand in req for req in required_tokens for cand in candidate_tokens if len(req) >= 3 and len(cand) >= 3):
            return True
    return False


def get_fallback_score(candidate: dict, jd_skills: list[str]) -> dict:
    candidate_skills = candidate.get("skills", [])
    required_skills = [skill for skill in jd_skills if str(skill).strip()]

    matched = [skill for skill in required_skills if skill_matches(skill, candidate_skills)]
    missing = [skill for skill in required_skills if skill not in matched]
    skill_score = int(len(matched) / len(required_skills) * 100) if required_skills else 50

    missing_title = [str(skill).strip() for skill in missing][:5]
    overlap_display = ", ".join(str(skill) for skill in matched[:5]) if matched else "none"
    missing_display = ", ".join(missing_title) if missing_title else "none"
    
    return {
        "skill_match_score": skill_score,
        "experience_synergy": 70,
        "fit_analysis": f"Evaluated via keyword heuristics. Overlapping skills: {overlap_display}. Missing skills: {missing_display}.",
        "missing_skills": missing_title,
        "match_percentage": int(skill_score * 0.6 + 70 * 0.4)
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
        try:
            parsed_jd = json.loads(jd_text)
            if isinstance(parsed_jd, dict):
                jd_text = f"Title: {parsed_jd.get('title')}\nSummary: {parsed_jd.get('summary')}\nRequirements: {parsed_jd.get('requirements')}"
        except Exception:
            pass

        # 1. Pre-score all candidates with fast keyword heuristics
        for cand in candidates:
            cand["heuristic"] = get_fallback_score(cand, jd_skills)

        # 2. Sort by heuristic match percentage descending
        candidates.sort(key=lambda x: x["heuristic"]["match_percentage"], reverse=True)

        # 3. Split into top 5 candidates for LLM scoring and remaining candidates
        top_n = 5
        to_llm = candidates[:top_n]
        remaining = candidates[top_n:]

        async def score_batch(batch: list[dict]) -> list[dict]:
            if not llm:
                return [{**cand, **cand["heuristic"]} for cand in batch]

            compact_candidates = [
                {
                    "id": cand["id"],
                    "skills": cand.get("skills", [])[:20],
                    "experience": cand.get("experience_level"),
                    "location": cand.get("location"),
                }
                for cand in batch
            ]
            user_content = json.dumps(
                {
                    "jd": {
                        "title": jd.title,
                        "requirements": jd_text[:1800],
                        "skills": jd_skills[:15],
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
