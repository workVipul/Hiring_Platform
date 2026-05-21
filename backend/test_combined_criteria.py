import httpx
import json

def build_flat_criteria(title, skills, location, seniority):
    clauses = []
    if title:
        clauses.append(f"((Designation:contains:{title}))")
    if skills:
        for skill in skills[:5]:
            clauses.append(f"((Skill_Set:contains:{skill}))")
    if seniority:
        clauses.append(f"((Experience_Level:contains:{seniority}))")
    if location:
        clauses.append(f"((Location:contains:{location}))")
        
    return "or".join(clauses)

url = "https://zohorecruit.thankfulrock-f57331b9.centralindia.azurecontainerapps.io/recruit/v2/Candidates/search"

# Try flat criteria
flat_criteria = build_flat_criteria(
    title="Java Developer",
    skills=["Java", "Spring Boot", "Hibernate"],
    location="Bangalore",
    seniority="Senior"
)
print("TRYING FLAT CRITERIA:", flat_criteria)

params = {
    "criteria": flat_criteria,
    "page": 1,
    "per_page": 20
}

try:
    response = httpx.get(url, params=params, timeout=30.0)
    print("STATUS CODE (FLAT):", response.status_code)
    data = response.json()
    candidates = data.get("data", [])
    print("CANDIDATES FETCHED (FLAT):", len(candidates))
except Exception as e:
    print("ERROR (FLAT):", e)
