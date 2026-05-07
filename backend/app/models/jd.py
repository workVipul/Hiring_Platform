from sqlalchemy import Column, Integer, String, DateTime, func

from app.db.session import Base


class JD(Base):
    """
    Represents a Job Description record in the database.

    Current phase: stores locally uploaded PDF files.
    Future phase: will store AI-generated JDs with additional fields
    (role, department, seniority, generated_content, status, etc.)

    To migrate to S3 later:
    - Keep `name` as-is (human-readable label)
    - Change `file_url` to store an S3 key like "uploads/jd_123.pdf"
    - Add a `storage_backend` column ("local" | "s3") if you need mixed storage
    - The frontend/API never changes — only the URL construction logic in the route changes
    """

    __tablename__ = "jd"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    # Stores the local path: "uploads/filename.pdf"
    # When you move to S3, this becomes the S3 object key or full URL.
    file_url = Column(String, nullable=False)

    # Audit timestamps — free metadata, always useful in production.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
