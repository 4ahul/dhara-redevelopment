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


def validate_config(settings: BaseSettings, keys: list[str]):
    """
    Verify that mandatory keys are present in the settings object.
    Logs a warning at startup if keys are missing but does not crash,
    allowing the service to boot (e.g. for Render health checks).
    """
    missing = [k for k in keys if not getattr(settings, k, None)]
    if missing:
        import logging
        logger = logging.getLogger("config")
        app_name = getattr(settings, "APP_NAME", "unknown_service")
        error_msg = (
            f"\n[CONFIG WARNING] The following environment variables are missing "
            f"for service '{app_name}':\n"
            + "\n".join([f" - {k}" for k in missing])
            + "\n\nPlease check your .env file or Render dashboard variables."
        )
        logger.warning(error_msg)

