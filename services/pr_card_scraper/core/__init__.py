import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "PR Card Scraper Service"
    APP_VERSION: str = "1.0.0"

    DATABASE_URL: str = (
        "postgresql://redevelopment:redevelopment@postgres:5432/redevelopment"
    )

    MAHABHUMI_URL: str = "https://bhulekh.mahabhumi.gov.in"

    TESSERACT_CMD: str = os.environ.get(
        "TESSERACT_CMD",
        "tesseract" if os.name != "nt" else r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    )

    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000

    # CAPTCHA solver — LLM Vision APIs
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
