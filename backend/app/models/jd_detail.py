from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Text, func

from app.db.session import Base


class JDDetail(Base):
    __tablename__ = "jd_details"

    id = Column(Integer, primary_key=True, index=True)
    jd_id = Column(Integer, ForeignKey("jds.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    context = Column(Text)
    skills = Column(JSON)
    resume_skills = Column(JSON)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
