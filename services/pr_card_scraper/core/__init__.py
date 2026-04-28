import os

from dhara_shared.core.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "pr_card_scraper"

    DATABASE_URL: str = "postgresql://redevelopment:redevelopment@localhost:5435/pr_card_scraper_db"

    MAHABHUMI_URL: str = "https://bhulekh.mahabhumi.gov.in"

    TESSERACT_CMD: str = os.environ.get(
        "TESSERACT_CMD",
        "tesseract" if os.name != "nt" else r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    )

    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000

    # CAPTCHA solver — LLM Vision APIs
    GEMINI_MODEL: str = "gemini-3.1-pro-preview"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    class Config(BaseServiceSettings.Config):
        env_file = BaseServiceSettings.get_env_file(__file__)


settings = Settings()


def get_gemini_model():
    """Get Gemini model name from settings."""
    return settings.GEMINI_MODEL
