import asyncio
import logging
import json
from app.llm.factory import get_llm_provider
from app.models.jd import JD

logger = logging.getLogger(__name__)

RANKING_SYSTEM = """You are an expert technical recruiter.
Analyze the candidate's profile details against the job description requirements.
Determine:
1. skill_match_score (0 to 100): How well do the candidate's skills match the JD's required skills?
2. experience_synergy (0 to 100): Does the candidate's experience level and history align with the seniority of the role?
3. fit_analysis: A concise, professional 2-3 sentence paragraph explaining why they fit, highlighting strengths and noting missing skills.
4. missing_skills: A list of key required skills from the JD that the candidate lacks.
5. match_percentage (0 to 100): A composite score representing overall fit.

You MUST return a valid JSON object only, matching this structure:
{
  "skill_match_score": int,
  "experience_synergy": int,
  "fit_analysis": str,
  "missing_skills": list[str],
  "match_percentage": int
}"""

def get_fallback_score(candidate: dict, jd_skills: list[str]) -> dict:
    cand_skills_set = {s.lower() for s in candidate.get("skills", [])}
    jd_skills_set = {s.lower() for s in jd_skills}
    
    overlap = cand_skills_set.intersection(jd_skills_set)
    skill_score = int(len(overlap) / len(jd_skills_set) * 100) if jd_skills_set else 50
    
    missing = list(jd_skills_set - cand_skills_set)
    missing_title = [s.title() for s in missing][:5]
    
    overlap_display = ", ".join(list(overlap)[:5]) if overlap else "none"
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

        async def score_single(cand: dict) -> dict:
            if not llm:
                scores = cand["heuristic"]
                return {**cand, **scores}
                
            user_content = f"""JOB DESCRIPTION:
Title: {jd.title}
Requirements / Context: {jd_text}
Key Required Skills: {', '.join(jd_skills)}

CANDIDATE PROFILE:
Name: {cand['full_name']}
Skills: {', '.join(cand['skills'])}
Experience Level: {cand['experience_level']}
Location: {cand['location']}
"""
            try:
                result = await llm.complete_json(system=RANKING_SYSTEM, user=user_content, max_tokens=1000)
                return {
                    **cand,
                    "skill_match_score": int(result.get("skill_match_score", 0)),
                    "experience_synergy": int(result.get("experience_synergy", 0)),
                    "fit_analysis": str(result.get("fit_analysis") or "No analysis generated."),
                    "missing_skills": list(result.get("missing_skills") or []),
                    "match_percentage": int(result.get("match_percentage", 0))
                }
            except Exception as e:
                logger.error(f"LLM ranking failed for candidate {cand['id']}: {e}")
                scores = cand["heuristic"]
                return {**cand, **scores}

        # 4. Run concurrent scoring tasks with a semaphore to limit concurrency
        sem = asyncio.Semaphore(2)
        async def score_with_sem(cand: dict) -> dict:
            async with sem:
                return await score_single(cand)
        tasks = [score_with_sem(c) for c in to_llm]
        ranked_top = await asyncio.gather(*tasks)

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
