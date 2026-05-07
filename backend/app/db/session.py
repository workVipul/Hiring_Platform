from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


# The engine is the raw connection to PostgreSQL.
# pool_pre_ping=True tests connections before using them — handles dropped connections gracefully.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# SessionLocal is a factory: call SessionLocal() to get a database session.
# autocommit=False means changes aren't saved until you explicitly call session.commit().
# autoflush=False means SQLAlchemy won't auto-sync state to DB mid-transaction.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base class that all SQLAlchemy models will inherit from.
# When you define class JD(Base), SQLAlchemy knows it maps to a DB table.
class Base(DeclarativeBase):
    pass


# FastAPI dependency — yields a DB session per request, then closes it automatically.
# Usage in routes: db: Session = Depends(get_db)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
