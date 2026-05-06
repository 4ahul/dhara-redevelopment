from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RecordOfRight(StrEnum):
    SEVEN_TWELVE = "7/12"
    EIGHT_A = "8A"
    PROPERTY_CARD = "Property Card"
    K_PRAT = "K-Prat"


class PRCardStatus(StrEnum):
    PROCESSING = "processing"
    CAPTCHA_REQUIRED = "captcha_required"
    COMPLETED = "completed"
    FAILED = "failed"


class PRCardRequest(BaseModel):
    """
    Input schema for PR Card extraction.

    Only district / taluka / village / survey_no are required.
    All other fields have sensible defaults so the orchestrator (and UI)
    can omit them unless they need something non-standard.
    """

    # ── Required location identifiers ────────────────────────────────────────
    district: str = Field(..., description="District name in English, e.g. 'pune'")
    taluka: str = Field(..., description="Taluka name in English, e.g. 'Haveli'")
    village: str = Field(..., description="Village name in English, e.g. 'Narhe'")
    survey_no: str = Field(..., description="Survey / CTS / Gat number, e.g. '1'")

    # ── Optional — fine to omit ───────────────────────────────────────────────
    survey_no_part1: str | None = Field(
        None,
        description="Part-1 of survey number when survey has sub-parts. "
        "If omitted, survey_no is used as Part-1.",
    )
    mobile: str = Field(
        "9999999999",
        description="Mobile number for OTP/verification field on the site. "
        "A valid 10-digit number; defaults to a placeholder.",
    )
    property_uid: str | None = Field(None, description="Property UID / ULPIN if already known")
    property_uid_known: bool = Field(
        False,
        description="Set True only if property_uid is being supplied",
    )
    language: str = Field(
        "EN",
        description="Output language: 'EN' (English) or 'MR' (Marathi). Default: EN",
    )
    record_of_right: RecordOfRight = Field(
        RecordOfRight.PROPERTY_CARD,
        description="Type of land record to fetch",
    )


class PRCardResponse(BaseModel):
    """
    Response schema for PR Card extraction.
    Works for both async (/scrape) and synchronous (/scrape/sync) endpoints.
    """

    id: str | None = None  # UUID — None for sync calls that skip DB
    status: PRCardStatus
    district: str
    taluka: str
    village: str
    survey_no: str
    created_at: datetime | None = None

    # ── Result payload ────────────────────────────────────────────────────────
    error_message: str | None = None
    image_url: str | None = None  # Source URL / "data:image/jpeg;base64"
    download_url: str | None = None  # Absolute URL to download via /download/{id}
    extracted_data: dict | None = None


class CaptchaSubmitRequest(BaseModel):
    pr_id: str
    captcha_value: str


class HealthResponse(BaseModel):
    status: str
    service: str
