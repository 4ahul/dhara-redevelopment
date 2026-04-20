"""
DP Report Service — Configuration
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "DP Report Service"
    APP_VERSION: str = "1.0.0"

    DATABASE_URL: str = (
        "postgresql://redevelopment:redevelopment@localhost:5435/dp_remarks_report_db"
    )

    # MCGM ArcGIS portal
    MCGM_PORTAL_URL: str = "https://mcgm.maps.arcgis.com"
    # DP 2034 webapp ID — override via env if you discover a better one
    MCGM_DP_WEBAPP_ID: str = ""

    # AutoDCR credentials (optional — for the authenticated DP remarks endpoint)
    AUTODCR_USERNAME: str = ""
    AUTODCR_PASSWORD: str = ""

    # DPRMarks portal credentials
    DPRMARKS_USERNAME: str = ""
    DPRMARKS_PASSWORD: str = ""

    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 60000  # ms

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
