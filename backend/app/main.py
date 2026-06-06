from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging

from app.core.config import settings
from app.db.session import Base, engine
from sqlalchemy import inspect, text

# Import all models so SQLAlchemy registers them before create_all runs.
# If you skip this, Base.metadata won't know about the JD table.
from app.models import jd, jd_detail, jd_template, user, user_access  # noqa: F401

# Import routers
from app.api.auth_routes import router as auth_router
from app.api.jd_routes import router as jd_router
from app.api.sourcing_routes import router as sourcing_router

# --- Existing AI routes (keep these) ---
# from app.api.routes import router as ai_router


app = FastAPI(
    title="NinjaForge API",
    description="AI-powered hiring platform",
    version="0.2.0",
)

# ---- CORS ----
# Allow the frontend (and Vercel preview URLs) to call the API.
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Static file serving for local uploads ----
# GET /uploads/filename.pdf will serve files from the uploads/ directory.
# In production with S3, remove this block — files are served from S3 directly.
uploads_dir = settings.UPLOADS_DIR
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# ---- Database setup ----
# Creates tables that don't exist yet. Safe to run on every startup.
# For production, replace with Alembic migrations.
Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)


def drop_legacy_jd_score_column() -> None:
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("jds")}
        if "jd_score" not in columns:
            return
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE jds DROP COLUMN jd_score"))
        logger.info("Dropped legacy jds.jd_score column.")
    except Exception as exc:
        logger.warning("Could not drop legacy jds.jd_score column: %s", exc)


def ensure_jd_template_module_column() -> None:
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("jd_templates")}
        if "module_name" in columns:
            return
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE jd_templates ADD COLUMN module_name VARCHAR(255)"))
        logger.info("Added jd_templates.module_name column.")
    except Exception as exc:
        logger.warning("Could not ensure jd_templates.module_name column: %s", exc)


drop_legacy_jd_score_column()
ensure_jd_template_module_column()

# ---- Routes ----
app.include_router(auth_router)
app.include_router(jd_router)
app.include_router(sourcing_router)
# app.include_router(ai_router)   # uncomment when ready


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}
