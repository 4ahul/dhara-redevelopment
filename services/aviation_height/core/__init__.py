from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "aviation_height"
    APP_VERSION: str = "1.0.0"
    GOOGLE_MAPS_API_KEY: str = ""
    SERP_API_KEY: str = ""

    class Config:
        import os
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        case_sensitive = True
        extra = "ignore"


settings = Settings()

