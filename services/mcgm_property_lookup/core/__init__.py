"""
MCGM Property Lookup — Configuration
"""

from dhara_shared.core.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "mcgm_property_lookup"

    # Load from this service's .env file
    DATABASE_URL: str = (
        "postgresql://redevelopment:redevelopment@postgres:5432/mcgm_property_lookup_db"
    )

    # ArcGIS / MCGM
    MCGM_WEBAPP_ID: str = "3a5c0a98a75341b985c10700dec6c4b8"
    MCGM_PORTAL_URL: str = "https://mcgm.maps.arcgis.com"
    MCGM_WEBAPP_URL: str = (
        "https://mcgm.maps.arcgis.com/apps/webappviewer/index.html"
        "?id=3a5c0a98a75341b985c10700dec6c4b8"
    )

    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 60000  # ms — generous for ArcGIS SPA

    class Config(BaseServiceSettings.Config):
        env_file = BaseServiceSettings.get_env_file(__file__)


settings = Settings()
