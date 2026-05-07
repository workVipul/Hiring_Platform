from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.jd import JD
from app.schemas.jd import JDCreate, JDListResponse, JDResponse

router = APIRouter(prefix="/api/v1/jds", tags=["JDs"])


@router.get("", response_model=JDListResponse)
def list_jds(db: Session = Depends(get_db)):
    """
    Return all JD records.

    Future: add query params for pagination, filtering by status, etc.
    Example: GET /api/v1/jds?skip=0&limit=20&status=draft
    """
    jds = db.query(JD).order_by(JD.created_at.desc()).all()
    return JDListResponse(items=jds, total=len(jds))


@router.get("/{jd_id}", response_model=JDResponse)
def get_jd(jd_id: int, db: Session = Depends(get_db)):
    """Return a single JD by ID."""
    jd = db.query(JD).filter(JD.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    return jd


@router.post("", response_model=JDResponse, status_code=201)
def create_jd(payload: JDCreate, db: Session = Depends(get_db)):
    """
    Create a JD record manually.
    Later this will be called automatically after an AI generation completes
    or after a file upload is processed.
    """
    jd = JD(name=payload.name, file_url=payload.file_url)
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return jd


@router.delete("/{jd_id}", status_code=204)
def delete_jd(jd_id: int, db: Session = Depends(get_db)):
    """Delete a JD record. Returns 204 No Content on success."""
    jd = db.query(JD).filter(JD.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    db.delete(jd)
    db.commit()
