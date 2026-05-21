import sys
import asyncio
from pathlib import Path

# Add backend to path so we can import app modules
backend_dir = Path("c:/Users/Wissen/Hiring_Platform/backend")
sys.path.append(str(backend_dir))

from app.services.zoho_service import ZohoRecruitService

async def main():
    print("Fetching candidates for skills: ['Java', 'Spring Boot']")
    candidates = await ZohoRecruitService.fetch_candidates(["Java", "Spring Boot"])
    print(f"Total candidates fetched: {len(candidates)}")
    if candidates:
        print("First candidate details:")
        for k, v in candidates[0].items():
            if k != "raw_profile":
                print(f"  {k}: {v}")
    else:
        print("No candidates fetched.")

if __name__ == "__main__":
    asyncio.run(main())
