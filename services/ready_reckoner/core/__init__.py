import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Premium Checker Service"
    APP_VERSION: str = "1.0.0"

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        case_sensitive = True
        extra = "ignore"


settings = Settings()
