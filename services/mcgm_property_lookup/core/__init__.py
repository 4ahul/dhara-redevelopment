"""
MCGM Property Lookup — Configuration
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "mcgm_property_lookup"
    APP_VERSION: str = "1.0.0"

    # Load from this service's .env file
    DATABASE_URL: str = "postgresql://redevelopment:redevelopment@localhost:5435/mcgm_property_lookup_db"

    # ArcGIS / MCGM
    MCGM_WEBAPP_ID: str = "3a5c0a98a75341b985c10700dec6c4b8"
    MCGM_PORTAL_URL: str = "https://mcgm.maps.arcgis.com"
    MCGM_WEBAPP_URL: str = (
        "https://mcgm.maps.arcgis.com/apps/webappviewer/index.html"
        "?id=3a5c0a98a75341b985c10700dec6c4b8"
    )

    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 60000  # ms — generous for ArcGIS SPA

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        case_sensitive = True
        extra = "ignore"


settings = Settings()

