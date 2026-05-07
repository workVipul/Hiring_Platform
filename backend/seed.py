"""
Run this once to populate the jd table with sample data:

    cd backend
    python seed.py

Safe to run multiple times — it checks before inserting.
"""

from app.db.session import SessionLocal, Base, engine
from app.models.jd import JD  # noqa — registers the model

# Ensure tables exist
Base.metadata.create_all(bind=engine)

SEED_DATA = [
    {
        "name": "Senior Java Developer_5 to 8 years",
        "file_url": "uploads/Senior Java Developer_5 to 8 years.pdf",
    },
    {
        "name": "Java Developer_Special Projects",
        "file_url": "uploads/Java Developer_Special Projects.pdf",
    },
    {
        "name": "Java Lead_JD",
        "file_url": "uploads/Java Lead_JD.pdf",
    },
    {
        "name": "Java Lead_Special Projects",
        "file_url": "uploads/Java Lead_Special Projects.pdf",
    },{
        "name": "Java_3 to 5 years",
        "file_url": "uploads/Java_3 to 5 years.pdf",
    },{
        "name": "PE-Job Description",
        "file_url": "uploads/PE-Job Description.pdf",
    },
]


def seed():
    db = SessionLocal()
    try:
        existing_count = db.query(JD).count()
        if existing_count > 0:
            print(f"Skipping seed — {existing_count} rows already exist in jd table.")
            return

        for data in SEED_DATA:
            db.add(JD(**data))

        db.commit()
        print(f"Seeded {len(SEED_DATA)} JD records successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
