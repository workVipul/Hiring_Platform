from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func

from app.db.session import Base


class JD(Base):
    __tablename__ = "jds"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ownership = Column(String(20), default="personal", nullable=False)
    jd_score = Column(SmallInteger)
    pdf_url = Column(String(1000))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
