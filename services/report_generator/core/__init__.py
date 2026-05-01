from dhara_shared.core.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "Report Generator Service"

    class Config(BaseServiceSettings.Config):
        env_file = BaseServiceSettings.get_env_file(__file__)


settings = Settings()
