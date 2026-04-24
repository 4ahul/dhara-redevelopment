"""
Dhara AI — Application Configuration
All settings loaded from environment variables with sensible defaults.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

_BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-pro-preview"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # ── Google Maps & Search ────────────────────────────
    GOOGLE_MAPS_API_KEY: str = ""
    SERP_API_KEY: str = ""

    # ── Clerk Auth ───────────────────────────────────────
    CLERK_SECRET_KEY: str = ""
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_JWT_KEY: str = ""
    CLERK_JWT_ISSUER: str = "clerk.accounts.dev"
    CLERK_API_BASE_URL: str = "https://api.clerk.com/v1"

    # ── Redis (Session Cache) ────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── PostgreSQL ───────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/orchestrator_db"
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # ── Cloudinary (File Storage) ────────────────────────
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_UPLOAD_PRESET: str = "dhara_uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # ── SMTP (Email) ────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@dharaai.com"
    SMTP_FROM_NAME: str = "Dhara AI"
    SMTP_USE_TLS: bool = True

    # ── Service URLs ─────────────────────────────────────
    SITE_ANALYSIS_URL: str = "http://localhost:8001"
    HEIGHT_URL: str = "http://localhost:8002"
    PREMIUM_URL: str = "http://localhost:8003"
    REPORT_URL: str = "http://localhost:8004"
    PR_CARD_URL: str = "http://localhost:8005"
    RAG_URL: str = "http://localhost:8009"
    MCGM_PROPERTY_URL: str = "http://localhost:8007"
    DP_REPORT_URL: str = "http://localhost:8008"
    READY_RECKONER_URL: str = "http://localhost:8003"

    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "Dhara AI Orchestrator"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    UPLOAD_DIR: str = str(_BASE_DIR / "uploads")
    REPORT_OUTPUT_DIR: str = str(_BASE_DIR / "reports")

    # ── Pagination Defaults ──────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    class Config:
        import os
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        case_sensitive = True
        extra = "ignore"


settings = Settings()


