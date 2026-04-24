import os
from pathlib import Path
from pydantic_settings import BaseSettings

class BaseServiceSettings(BaseSettings):
    """
    Standardized configuration base for all Dhara AI microservices.
    Handles absolute .env resolution and common app metadata.
    """
    APP_NAME: str = "dhara_service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Common API Keys that might be needed by multiple services
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    SERP_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""

    class Config:
        case_sensitive = True
        extra = "ignore"

        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            return init_settings, env_settings, file_secret_settings

    @classmethod
    def get_env_file(cls, caller_file: str) -> str:
        """
        Helper to resolve the absolute path to the local .env file.
        Usage: env_file = Settings.get_env_file(__file__)
        """
        return str(Path(os.path.abspath(caller_file)).resolve().parents[1] / ".env")
