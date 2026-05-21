from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.db.session import Base, engine

# Import all models so SQLAlchemy registers them before create_all runs.
# If you skip this, Base.metadata won't know about the JD table.
from app.models import jd, jd_detail, user, user_access  # noqa: F401

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

# ---- Routes ----
app.include_router(auth_router)
app.include_router(jd_router)
app.include_router(sourcing_router)
# app.include_router(ai_router)   # uncomment when ready


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}
