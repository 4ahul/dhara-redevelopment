from pydantic import Field

from dhara_shared.core.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "ocr_service"
    APP_VERSION: str = "1.0.0"
    GOOGLE_API_KEY: str = Field(default="", env="GOOGLE_API_KEY")

    class Config(BaseServiceSettings.Config):
        env_file = BaseServiceSettings.get_env_file(__file__)


settings = Settings()
