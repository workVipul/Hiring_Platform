import sys
import json
from pathlib import Path

# Add backend to path
sys.path.append("c:/Users/Wissen/Hiring_Platform/backend")

from app.services.pdf_service import write_simple_pdf

jd_content = {
    "summary": "Wissen Technology is hiring an experienced Java Architect to design, develop, and guide scalable enterprise applications. The role involves defining architecture, mentoring teams, and ensuring best practices across the development lifecycle.",
    "skills": ["Java", "Spring Boot", "Microservices", "Kubernetes", "AWS"],
    "soft_skills": ["Strong communication and stakeholder management", "Ability to mentor junior developers"],
    "metadata": {
        "experience_years": "12+ years",
        "location": "Bangalore"
    }
}

try:
    print("Generating PDF...")
    pdf_path = write_simple_pdf(
        title="Java Architect",
        content=json.dumps(jd_content),
        jd_id=999
    )
    print("SUCCESS! PDF Generated at:", pdf_path)
    file_path = Path("c:/Users/Wissen/Hiring_Platform/backend") / pdf_path
    print("PDF File Exists:", file_path.exists(), "Size:", file_path.stat().st_size if file_path.exists() else 0)
except Exception as e:
    print("ERROR GENERATING PDF:", e)
