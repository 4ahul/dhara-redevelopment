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
    
    # Common API Keys
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    SERP_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""
    SENTRY_DSN: str = ""

    def validate_critical_keys(self, keys: list[str]):
        """
        Verify that mandatory keys are present.
        Used at startup to prevent silent failures.
        """
        missing = [k for k in keys if not getattr(self, k, None)]
        if missing:
            error_msg = (
                f"\n[CRITICAL CONFIG ERROR] The following environment variables are missing "
                f"for service '{self.APP_NAME}':\n"
                + "\n".join([f" - {k}" for k in missing])
                + "\n\nPlease check your .env file or Docker environment."
            )
            # We raise a RuntimeError so the container fails to start
            raise RuntimeError(error_msg)

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
