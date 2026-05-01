"""
DP Report Service — Configuration
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "dp_remarks_report"
    APP_VERSION: str = "1.0.0"

    DATABASE_URL: str = (
        "postgresql://redevelopment:redevelopment@localhost:5435/dp_remarks_report_db"
    )

    # MCGM ArcGIS portal
    MCGM_PORTAL_URL: str = "https://mcgm.maps.arcgis.com"
    MCGM_DP_WEBAPP_ID: str = ""

    # AutoDCR credentials (optional)
    AUTODCR_USERNAME: str = ""
    AUTODCR_PASSWORD: str = ""

    # DPRMarks portal credentials
    DPRMARKS_USERNAME: str = ""
    DPRMARKS_PASSWORD: str = ""
    DPRMARKS_CONSUMER_NAME: str = "Dhiraj Kunj CHS"
    DPRMARKS_CONSUMER_MOBILE: str = "9999999999"
    DPRMARKS_CONSUMER_EMAIL: str = ""

    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 60000  # ms

    # Payment automation
    SKIP_PAYMENT: bool = False
    TEST_DP_PDF_PATH: str = ""
    BUSINESS_UPI_VPA: str = ""
    PAYMENT_TIMEOUT_SECONDS: int = 300
    PAYMENT_QUEUE_WAIT_SECONDS: int = 600
    REDIS_URL: str = "redis://localhost:6379/0"

    # Payment method: "upi" (default) or "wallet"
    PAYMENT_METHOD: str = "upi"
    # Wallet type when PAYMENT_METHOD is "wallet": "phonepe", "paytm", "amazonpay", "mobikwik", "airtelmoney", "freecharge", "jioMoney", "olamoney", "axisbank", "kvi"
    WALLET_TYPE: str = "phonepe"

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"),
        "extra": "ignore",
    }


settings = Settings()
