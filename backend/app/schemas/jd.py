from datetime import datetime
from pydantic import BaseModel


# --- Request schemas (what the API accepts) ---

class JDCreate(BaseModel):
    """Used when inserting a new JD record (e.g., after a file upload)."""
    name: str
    file_url: str


# --- Response schemas (what the API returns) ---

class JDResponse(BaseModel):
    """
    Shape of a single JD record returned by the API.
    The frontend TypeScript interface should mirror this exactly.
    """
    id: int
    name: str
    file_url: str
    created_at: datetime
    updated_at: datetime

    # from_attributes=True (formerly orm_mode) allows Pydantic to read
    # SQLAlchemy ORM objects directly instead of requiring plain dicts.
    model_config = {"from_attributes": True}


class JDListResponse(BaseModel):
    """Wrapper for list endpoints — makes it easy to add pagination later."""
    items: list[JDResponse]
    total: int