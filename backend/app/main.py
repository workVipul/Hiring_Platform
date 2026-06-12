from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import os
import logging

from app.core.config import settings
from app.db.session import Base, SessionLocal, engine
from sqlalchemy import inspect, text

# Import all models so SQLAlchemy registers them before create_all runs.
# If you skip this, Base.metadata won't know about the JD table.
from app.models import candidate_ownership, jd, jd_detail, jd_template, user, user_access  # noqa: F401
from app.services.ownership_service import ensure_sla_seed_data, expire_due_ownerships

# Import routers
from app.api.auth_routes import router as auth_router
from app.api.jd_routes import router as jd_router
from app.api.ownership_routes import router as ownership_router
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
        with engine.begin() as connection:
            if "definition_json" not in columns:
                connection.execute(text("ALTER TABLE jd_templates ADD COLUMN definition_json JSON"))
                logger.info("Added jd_templates.definition_json column.")
            if "version" not in columns:
                connection.execute(text("ALTER TABLE jd_templates ADD COLUMN version INTEGER DEFAULT 1 NOT NULL"))
                logger.info("Added jd_templates.version column.")
            if "template_html" not in columns:
                connection.execute(text("ALTER TABLE jd_templates ADD COLUMN template_html TEXT"))
                logger.info("Added jd_templates.template_html column.")
            if "template_css" not in columns:
                connection.execute(text("ALTER TABLE jd_templates ADD COLUMN template_css TEXT"))
                logger.info("Added jd_templates.template_css column.")
            if "mapped_fields" not in columns:
                connection.execute(text("ALTER TABLE jd_templates ADD COLUMN mapped_fields JSON"))
                logger.info("Added jd_templates.mapped_fields column.")
            if "layout_metadata" not in columns:
                connection.execute(text("ALTER TABLE jd_templates ADD COLUMN layout_metadata JSON"))
                logger.info("Added jd_templates.layout_metadata column.")
            if "template_quality_score" not in columns:
                connection.execute(text("ALTER TABLE jd_templates ADD COLUMN template_quality_score JSON"))
                logger.info("Added jd_templates.template_quality_score column.")
    except Exception as exc:
        logger.warning("Could not ensure jd_templates custom template columns: %s", exc)


def ensure_ownership_constraints() -> None:
    try:
        with engine.begin() as connection:
            inspector = inspect(engine)
            columns = {column["name"] for column in inspector.get_columns("sla_rules")}
            if "blueprint" not in columns:
                connection.execute(text("ALTER TABLE sla_rules ADD COLUMN blueprint VARCHAR(40) DEFAULT 'SCR' NOT NULL"))
                logger.info("Added sla_rules.blueprint column.")
            if engine.dialect.name != "postgresql":
                return
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_candidate_ownership_active_candidate "
                    "ON candidate_ownership (zoho_candidate_id) WHERE status = 'ACTIVE'"
                )
            )
    except Exception as exc:
        logger.warning("Could not ensure candidate ownership constraints: %s", exc)


def seed_sla_rules() -> None:
    db = SessionLocal()
    try:
        ensure_sla_seed_data(db)
    except Exception as exc:
        logger.warning("Could not seed SLA rules: %s", exc)
    finally:
        db.close()


async def ownership_expiry_loop() -> None:
    while True:
        await asyncio.sleep(60 * 60)
        db = SessionLocal()
        try:
            count = expire_due_ownerships(db)
            if count:
                logger.info("Expired %s candidate ownership records.", count)
        except Exception as exc:
            logger.warning("Candidate ownership expiry job failed: %s", exc)
        finally:
            db.close()


drop_legacy_jd_score_column()
ensure_jd_template_module_column()
ensure_ownership_constraints()
seed_sla_rules()


@app.on_event("startup")
async def start_background_jobs():
    asyncio.create_task(ownership_expiry_loop())

# ---- Routes ----
app.include_router(auth_router)
app.include_router(jd_router)
app.include_router(sourcing_router)
app.include_router(ownership_router)
# app.include_router(ai_router)   # uncomment when ready


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}
