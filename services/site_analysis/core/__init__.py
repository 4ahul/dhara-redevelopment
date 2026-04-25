from dhara_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "site_analysis"
    APP_VERSION: str = "1.0.0"

    class Config(BaseServiceSettings.Config):
        env_file = BaseServiceSettings.get_env_file(__file__)


settings = Settings()


