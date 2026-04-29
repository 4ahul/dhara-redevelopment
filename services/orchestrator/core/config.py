import os
from pathlib import Path

from dhara_shared.core.config import BaseServiceSettings

_BASE_DIR = Path(__file__).resolve().parents[1]


def _is_docker():
    return os.path.exists("/.dockerenv")


_HOST = "localhost" if not _is_docker() else ""


class Settings(BaseServiceSettings):
    # ── LLM ──────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-pro-preview"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # ── Google Maps & Search ────────────────────────────

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
        "postgresql+asyncpg://redevelopment:redevelopment@localhost:5435/orchestrator_db"
    )

    @property
    def db_url(self) -> str:
        """Uses DATABASE_URL as provided, only mapping localhost to postgres for local Docker Compose development."""
        url = self.DATABASE_URL
        # If we are on Render, use the URL as-is but ensure +asyncpg driver is present
        if os.environ.get("RENDER"):
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        # Fallback for local Docker Compose
        if _is_docker():
            url = (
                url.replace("localhost", "postgres")
                .replace("127.0.0.1", "postgres")
                .replace(":5435", ":5432")
            )
        return url

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
    # Set True during testing to skip Cloudinary upload and keep reports local
    SAVE_REPORTS_LOCALLY: bool = True

    # ── SMTP (Email) ────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@dharaai.com"
    SMTP_FROM_NAME: str = "Dhara AI"
    SMTP_USE_TLS: bool = True

    # ── Service URLs ─────────────────────────────────────
    SITE_ANALYSIS_URL: str = f"http://{_HOST or 'site_analysis'}:8001"
    HEIGHT_URL: str = f"http://{_HOST or 'aviation_height'}:8002"
    PREMIUM_URL: str = f"http://{_HOST or 'ready_reckoner'}:8003"
    REPORT_URL: str = f"http://{_HOST or 'report_generator'}:8004"
    PR_CARD_URL: str = f"http://{_HOST or 'pr_card_scraper'}:8005"
    RAG_URL: str = f"http://{_HOST or 'rag_service'}:8006"
    MCGM_PROPERTY_URL: str = f"http://{_HOST or 'mcgm_property_lookup'}:8007"
    DP_REPORT_URL: str = f"http://{_HOST or 'dp_remarks_report'}:8008"
    READY_RECKONER_URL: str = f"http://{_HOST or 'ready_reckoner'}:8003"
    OCR_URL: str = f"http://{_HOST or 'ocr_service'}:8009"

    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "orchestrator"
    APP_VERSION: str = "3.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    UPLOAD_DIR: str = str(_BASE_DIR / "uploads")
    REPORT_OUTPUT_DIR: str = str(_BASE_DIR / "reports")

    # ── Pagination Defaults ──────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    class Config(BaseServiceSettings.Config):
        env_file = BaseServiceSettings.get_env_file(__file__)


settings = Settings()
