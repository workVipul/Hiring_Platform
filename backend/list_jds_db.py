import sys
sys.path.append("c:/Users/Wissen/Hiring_Platform/backend")

from app.db.session import SessionLocal
from app.models.jd import JD

db = SessionLocal()
try:
    jds = db.query(JD).all()
    print("Found JDs in Database:")
    for jd in jds:
        print(f"ID: {jd.id}, Title: {jd.title}, Ownership: {jd.ownership}")
finally:
    db.close()
