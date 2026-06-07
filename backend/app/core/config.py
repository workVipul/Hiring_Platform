from pydantic import model_validator
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
    LLM_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    GROQ_API_KEY: str = ""
    GROK_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Zoho portal candidates search demo configuration
    ZOHO_BASE_URL: str = "https://zohorecruit.thankfulrock-f57331b9.centralindia.azurecontainerapps.io/recruit/v2/Candidates"
    ZOHO_JOB_OPENINGS_URL: str = "https://zohorecruit.thankfulrock-f57331b9.centralindia.azurecontainerapps.io/recruit/v2/Job_Openings"
    ZOHO_API_KEY: str = ""
    ZOHO_CLIENT_ID: str = ""
    ZOHO_CLIENT_SECRET: str = ""
    ZOHO_REFRESH_TOKEN: str = ""
    ZOHO_ACCOUNTS_URL: str = "https://accounts.zoho.com"

    # Sourcing pipeline thresholds
    SOURCING_MAX_ZOHO_PAGES: int = 5
    SOURCING_ZOHO_PAGE_SIZE: int = 100
    SOURCING_SCORING_LIMIT: int = 500
    SOURCING_LLM_RANK_LIMIT: int = 50
    SOURCING_RESULT_LIMIT: int = 50

    @model_validator(mode="after")
    def validate_provider_configuration(self):
        if self.LLM_PROVIDER.lower() == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        return self

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
