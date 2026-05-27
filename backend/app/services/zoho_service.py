import logging
import asyncio
import time
import re
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

def build_criteria(
    skills: list[str],
    title: str | None = None,
    location: str | None = None,
    seniority: str | None = None
) -> str:
    groups = []

    # 1. Skills are the safest pre-ranking filter. Use OR inside the skill group,
    # then AND the group with location/seniority when provided.
    if skills:
        clean_skills = [s.strip() for s in skills if s.strip()]
        skill_clauses = [f"((Skill_Set:contains:{skill}))" for skill in clean_skills[:5]]
        if skill_clauses:
            groups.append("(" + "or".join(skill_clauses) + ")")
            
    # 2. Location. The mock Zoho API stores location across City/State/Country,
    # not a single Location field.
    if location:
        location_clauses = []
        for term in location_terms(location):
            location_clauses.extend([
                f"((City:contains:{term}))",
                f"((State:contains:{term}))",
                f"((Country:contains:{term}))",
            ])
        if location_clauses:
            groups.append("(" + "or".join(location_clauses) + ")")
            
    if not groups:
        return ""
        
    return "and".join(groups)


def normalize_location(value: str) -> str:
    # Zoho often stores city only; avoid filtering on long "City, State, Country" strings.
    return value.split(",")[0].strip()


def location_terms(value: str) -> list[str]:
    raw_terms = [part.strip() for part in value.split(",") if part.strip()]
    if not raw_terms:
        raw_terms = [value.strip()]
    terms = []
    for term in raw_terms:
        terms.append(term)
        lowered = term.lower()
        if lowered == "bangalore":
            terms.append("Bengaluru")
        elif lowered == "bengaluru":
            terms.append("Bangalore")
    seen = set()
    return [term for term in terms if term and not (term.lower() in seen or seen.add(term.lower()))]


def seniority_to_zoho_levels(value: str) -> list[str]:
    lowered = value.lower().strip()
    if not lowered:
        return []
    if "principal" in lowered or "architect" in lowered or "lead" in lowered:
        return ["Lead", "Senior"]
    if "senior" in lowered or "sr" in lowered:
        return ["Senior", "Lead"]
    if "junior" in lowered or "jr" in lowered or "fresher" in lowered:
        return ["Junior"]
    if "mid" in lowered:
        return ["Mid", "Senior"]

    years = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", lowered)]
    if not years:
        return [value.strip()]
    minimum = min(years)
    if minimum >= 8:
        return ["Senior", "Lead"]
    if minimum >= 4:
        return ["Mid", "Senior"]
    return ["Junior", "Mid"]

class ZohoRecruitService:
    _cached_token = None
    _token_expiry = 0.0

    @classmethod
    async def get_access_token(cls) -> str:
        # Prioritize static API key/token if explicitly set
        if settings.ZOHO_API_KEY:
            return settings.ZOHO_API_KEY

        # Dynamic OAuth2 flow
        if settings.ZOHO_CLIENT_ID and settings.ZOHO_CLIENT_SECRET and settings.ZOHO_REFRESH_TOKEN:
            if cls._cached_token and time.time() < cls._token_expiry:
                return cls._cached_token

            try:
                async with httpx.AsyncClient() as client:
                    accounts_url = getattr(settings, "ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com")
                    token_url = f"{accounts_url.rstrip('/')}/oauth/v2/token"
                    
                    data = {
                        "refresh_token": settings.ZOHO_REFRESH_TOKEN,
                        "client_id": settings.ZOHO_CLIENT_ID,
                        "client_secret": settings.ZOHO_CLIENT_SECRET,
                        "grant_type": "refresh_token"
                    }
                    
                    response = await client.post(token_url, data=data, timeout=15.0)
                    response.raise_for_status()
                    res_data = response.json()
                    
                    if "access_token" in res_data:
                        cls._cached_token = res_data["access_token"]
                        expires_in = res_data.get("expires_in", 3600)
                        cls._token_expiry = time.time() + expires_in - 300
                        logger.info("Successfully refreshed Zoho OAuth2 access token.")
                        return cls._cached_token
                    else:
                        logger.error(f"Zoho OAuth token response missing access_token: {res_data}")
            except Exception as e:
                logger.error(f"Failed to refresh Zoho OAuth2 token: {e}")
        
        return ""

    @classmethod
    async def fetch_candidates(
        cls,
        skills: list[str],
        title: str | None = None,
        location: str | None = None,
        seniority: str | None = None,
        page: int = 1,
        per_page: int = 20,
        all_candidates: bool = False,
    ) -> list[dict]:
        criteria = build_criteria(skills, title, location, seniority)
        if not criteria and not all_candidates:
            return []

        # Construct request URL
        url = settings.ZOHO_BASE_URL.rstrip("/") if all_candidates else f"{settings.ZOHO_BASE_URL.rstrip('/')}/search"
        params = {
            "page": page,
            "per_page": per_page
        }
        if not all_candidates:
            params["criteria"] = criteria

        headers = {}
        access_token = await cls.get_access_token()
        if access_token:
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            headers["X-API-KEY"] = access_token

        # Retry logic with exponential backoff
        max_retries = 3
        backoff = 1.0 # starting delay in seconds

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, params=params, headers=headers, timeout=30.0)
                    
                    if response.status_code == 429:
                        logger.warning(f"Zoho API returned 429 (Too Many Requests), retrying attempt {attempt}/{max_retries} after {backoff}s...")
                        await asyncio.sleep(backoff)
                        backoff *= 2.0
                        continue
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    # Extract list of candidates
                    candidates = data.get("data", [])
                    if not isinstance(candidates, list):
                        return []
                        
                    # Normalize candidate data to prevent frontend crashes
                    normalized = []
                    for c in candidates:
                        # Extract first and last name safely
                        first_name = c.get("First_Name") or ""
                        last_name = c.get("Last_Name") or ""
                        full_name = f"{first_name} {last_name}".strip() or "Anonymous Candidate"

                        # Location resilient mapping
                        loc_parts = []
                        for key in ["Location", "City", "State", "Country"]:
                            val = c.get(key)
                            if val:
                                loc_parts.append(str(val))
                        location_val = ", ".join(loc_parts) if loc_parts else "N/A"

                        # Experience resilient mapping
                        exp_val = c.get("Experience_Level")
                        if not exp_val:
                            exp_years = c.get("Experience_in_Years")
                            if exp_years is not None:
                                exp_val = f"{exp_years} Years"
                            else:
                                exp_val = "N/A"

                        normalized.append({
                            "id": str(c.get("id") or ""),
                            "full_name": full_name,
                            "email": c.get("Email") or "N/A",
                            "mobile": c.get("Mobile") or c.get("Phone") or "N/A",
                            "skills": [s.strip() for s in (c.get("Skill_Set") or "").split(",") if s.strip()],
                            "experience_level": exp_val,
                            "location": location_val,
                            "raw_profile": c # keep full record for ranking context
                        })
                    return normalized

            except httpx.HTTPStatusError as e:
                logger.error(f"Zoho HTTP error: {e.response.status_code} - {e.response.text}")
                if attempt == max_retries:
                    break
            except Exception as e:
                logger.error(f"Zoho request error on attempt {attempt}: {e}")
                if attempt == max_retries:
                    break
            
            # Backoff for general network errors
            await asyncio.sleep(backoff)
            backoff *= 2.0

        return []
