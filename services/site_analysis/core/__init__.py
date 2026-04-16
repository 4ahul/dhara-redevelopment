import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GOOGLE_MAPS_API_KEY: str = ""  # SerpApi key
    SERP_API_KEY: str = ""
    APP_NAME: str = "Site Analysis Service"
    APP_VERSION: str = "1.0.0"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
