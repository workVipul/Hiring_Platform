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
        "name": "Senior Backend Engineer JD",
        "file_url": "uploads/senior_backend_engineer.pdf",
    },
    {
        "name": "Product Manager — Growth",
        "file_url": "uploads/pm_growth.pdf",
    },
    {
        "name": "Frontend Engineer (React)",
        "file_url": "uploads/frontend_engineer_react.pdf",
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
