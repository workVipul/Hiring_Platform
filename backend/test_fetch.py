import httpx
import json

url = "https://zohorecruit.thankfulrock-f57331b9.centralindia.azurecontainerapps.io/recruit/v2/Candidates/search"
params = {
    "criteria": "((Designation:contains:Java Developer))or((Skill_Set:contains:Java))or((Skill_Set:contains:Object-Oriented Programming))or((Skill_Set:contains:Data Structures))or((Experience_Level:contains:Senior))or((Location:contains:Bangalore))",
    "page": 1,
    "per_page": 20
}

try:
    response = httpx.get(url, params=params, timeout=30.0)
    print("STATUS CODE:", response.status_code)
    data = response.json()
    print("KEYS IN DATA:", data.keys())
    candidates = data.get("data", [])
    print("CANDIDATES COUNT:", len(candidates))
    if candidates:
        print("FIRST CANDIDATE SAMPLE:")
        print(json.dumps(candidates[0], indent=2))
except Exception as e:
    print("ERROR:", e)
