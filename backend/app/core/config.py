from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Existing key — keep compatible with current repo
    ANTHROPIC_API_KEY: str = ""

    # New: database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/jdforge"

    # New: local upload path (relative to backend root)
    UPLOADS_DIR: str = "uploads"

    # Existing: CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
