"""
Seed demo accounts and one JD row per PDF in backend/uploads.

Accounts:
    admin@example.com / password123  -> admin, sees all JDs
    demo@example.com  / password123  -> normal, sees public + own personal JDs
"""

from pathlib import Path

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models.jd import JD
from app.models.jd_detail import JDDetail
from app.models.candidate_ownership import CandidateOwnership, OwnershipHistory, SLARule  # noqa: F401
from app.models.user import User
from app.models.user_access import UserAccess
from app.services.ownership_service import ensure_sla_seed_data


Base.metadata.create_all(bind=engine)

USERS = [
    {"name": "Admin Recruiter", "email": "admin@example.com", "password": "password123", "access_type": "admin"},
    {"name": "Demo Recruiter", "email": "demo@example.com", "password": "password123", "access_type": "normal"},
]


def title_from_pdf(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " - ")


def ensure_user(db, user_data: dict) -> User:
    user = db.query(User).filter(User.email == user_data["email"]).first()
    if not user:
        user = User(
            name=user_data["name"],
            email=user_data["email"],
            password_hash=hash_password(user_data["password"]),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created {user_data['access_type']} user: {user.email}")

    access = db.query(UserAccess).filter(UserAccess.user_id == user.id).first()
    if not access:
        db.add(UserAccess(user_id=user.id, access_type=user_data["access_type"]))
    else:
        access.access_type = user_data["access_type"]
    db.commit()
    return user


def upsert_detail(db, jd: JD, context: str, skills: list[str], metadata: dict):
    detail = db.query(JDDetail).filter(JDDetail.jd_id == jd.id).first()
    if not detail:
        detail = JDDetail(jd_id=jd.id)
        db.add(detail)
    detail.context = context
    detail.skills = skills
    detail.resume_skills = []
    detail.metadata_json = metadata


def seed():
    db = SessionLocal()
    try:
        admin = ensure_user(db, USERS[0])
        ensure_user(db, USERS[1])
        ensure_sla_seed_data(db)

        uploads_dir = Path(settings.UPLOADS_DIR)
        pdfs = sorted(uploads_dir.glob("*.pdf"))
        inserted = 0
        detailed = 0

        for pdf in pdfs:
            pdf_url = f"uploads/{pdf.name}"
            jd = db.query(JD).filter(JD.pdf_url == pdf_url).first()
            if not jd:
                jd = JD(
                    title=title_from_pdf(pdf),
                    content=f"Source JD uploaded from {pdf.name}.",
                    ownership="public",
                    pdf_url=pdf_url,
                    created_by=admin.id,
                )
                db.add(jd)
                db.commit()
                db.refresh(jd)
                inserted += 1
            else:
                jd.ownership = "public"
                jd.created_by = admin.id

            upsert_detail(
                db,
                jd,
                context=f"Seeded from uploaded PDF: {pdf.name}",
                skills=[],
                metadata={"source": "uploaded_pdf", "filename": pdf.name, "size_bytes": pdf.stat().st_size},
            )
            detailed += 1

        db.commit()
        print(f"Seeded {inserted} uploaded PDF JDs. Ensured details for {detailed} PDFs.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
