from dhara_shared.core.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "site_analysis"

    # ── Geographic Constraints ──────────────────────────────────────────
    MUMBAI_CENTER_LAT: float = 19.0760
    MUMBAI_CENTER_LNG: float = 72.8777
    MUMBAI_RADIUS_METERS: int = 30000

    # ── ArcGIS Protocol Defaults ────────────────────────────────────────
    ARCGIS_SR_CODE: int = 4326  # WGS84
    ARCGIS_FORMAT: str = "json"

    class Config(BaseServiceSettings.Config):
        env_file = BaseServiceSettings.get_env_file(__file__)


settings = Settings()
