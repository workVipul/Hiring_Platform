from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/jdforge"
    UPLOADS_DIR: str = "uploads"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Auth
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    # LLM provider configuration
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_API_KEY: str = ""
    GROK_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Zoho portal candidates search demo configuration
    ZOHO_BASE_URL: str = "https://zohorecruit.thankfulrock-f57331b9.centralindia.azurecontainerapps.io/recruit/v2/Candidates"
    ZOHO_API_KEY: str = ""
    ZOHO_CLIENT_ID: str = ""
    ZOHO_CLIENT_SECRET: str = ""
    ZOHO_REFRESH_TOKEN: str = ""
    ZOHO_ACCOUNTS_URL: str = "https://accounts.zoho.com"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
