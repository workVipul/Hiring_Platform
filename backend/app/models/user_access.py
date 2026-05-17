from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.db.session import Base


class UserAccess(Base):
    __tablename__ = "user_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    access_type = Column(String(20), default="normal", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
