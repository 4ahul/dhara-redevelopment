from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --- Sub-models -----------------------------------------------------------


class PointOfContact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    contact_person: str = Field(alias="contactPerson")
    contact_mail: str | None = Field(None, alias="contactMail")
    contact_phone: str | None = Field(None, alias="contactPhone")


# --- Society -----------------------------------------------------------------

VALID_STATUSES = {
    "New",
    "Report Draft",
    "Report Approved",
    "Tender Draft",
    "Tender Live",
    "Tender Review Pending",
    "Builder Selected",
}


class SocietyCreate(BaseModel):
    """Accepts both camelCase (frontend) and snake_case (internal) field names."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=2, max_length=500)
    # Frontend sends "location"; internal callers can use "address"
    address: str = Field(min_length=5, max_length=2000, alias="location")
    registration_number: str | None = Field(None, alias="registrationNumber", max_length=255)
    # Frontend sends "initialStatus"; defaults to "New"
    status: str = Field("New", alias="initialStatus")
    # Frontend sends "totalFlats"; internal callers can use "num_flats"
    num_flats: int | None = Field(None, alias="totalFlats", ge=0)
    num_commercial: int | None = Field(default=None, ge=0)
    # Frontend sends Unix timestamp (ms or s); service converts to datetime
    onboarded_date_ts: int | None = Field(None, alias="onboardedDate")
    # Array of contacts; first entry maps to flat poc columns
    point_of_contact: list[PointOfContact] = Field(default_factory=list, alias="pointOfContact")
    notes: str | None = None
    # Flat POC fields kept for backward-compat with internal callers
    poc_name: str | None = Field(default=None, max_length=255)
    poc_phone: str | None = Field(default=None, max_length=50)
    poc_email: str | None = Field(default=None, max_length=255)
    # Standard optional fields (unchanged)
    onboarded_date: datetime | None = None
    cts_no: str | None = Field(default=None, max_length=100)
    fp_no: str | None = Field(default=None, max_length=100)
    tps_name: str | None = Field(default=None, max_length=255)
    ward: str | None = Field(default=None, max_length=20, description="Auto-resolved from address")
    village: str | None = Field(
        default=None, max_length=255, description="Auto-resolved from address"
    )
    taluka: str | None = Field(default=None, max_length=255)
    district: str | None = Field(default=None, max_length=255)
    plot_area_sqm: float | None = Field(default=None, ge=0)
    plot_area_with_tp: float | None = Field(default=None, ge=0)
    road_width_m: float | None = Field(default=None, ge=0)
    residential_area_sqft: float | None = Field(default=None, ge=0)
    commercial_area_sqft: float | None = Field(default=None, ge=0)
    sale_rate: float | None = Field(default=None, ge=0)
    society_age: int | None = Field(
        default=None, ge=0, description="Year OC was issued or years since"
    )
    existing_bua_sqft: float | None = Field(
        default=None, ge=0, description="Existing Built Up Area in sq ft"
    )
    pfa_sqft: float | None = Field(default=None, ge=0, description="PFA from original OC in sq ft")
    ocr_data: dict | None = Field(default=None, description="Raw OCR output from document scan")


class SocietyUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=2000)
    registration_number: str | None = Field(default=None, max_length=255)
    poc_name: str | None = Field(default=None, max_length=255)
    poc_phone: str | None = Field(default=None, max_length=50)
    poc_email: str | None = Field(default=None, max_length=255)
    onboarded_date: datetime | None = None
    notes: str | None = None
    cts_no: str | None = Field(default=None, max_length=100)
    fp_no: str | None = Field(default=None, max_length=100)
    tps_name: str | None = Field(default=None, max_length=255)
    cts_validated: str | None = Field(default=None, max_length=20)
    ward: str | None = Field(default=None, max_length=20)
    village: str | None = Field(default=None, max_length=255)
    taluka: str | None = Field(default=None, max_length=255)
    district: str | None = Field(default=None, max_length=255)
    plot_area_sqm: float | None = Field(default=None, ge=0)
    plot_area_with_tp: float | None = Field(default=None, ge=0)
    road_width_m: float | None = Field(default=None, ge=0)
    num_flats: int | None = Field(default=None, ge=0)
    num_commercial: int | None = Field(default=None, ge=0)
    residential_area_sqft: float | None = Field(default=None, ge=0)
    commercial_area_sqft: float | None = Field(default=None, ge=0)
    sale_rate: float | None = Field(default=None, ge=0)
    status: str | None = None
    lat: float | None = None
    lng: float | None = None


class SocietyResponse(BaseModel):
    id: UUID
    name: str
    address: str
    registration_number: str | None = None
    poc_name: str | None = None
    poc_phone: str | None = None
    poc_email: str | None = None
    onboarded_date: datetime | None = None
    notes: str | None = None
    cts_no: str | None = None
    fp_no: str | None = None
    tps_name: str | None = None
    cts_validated: str | None = None
    ward: str | None = None
    village: str | None = None
    taluka: str | None = None
    district: str | None = None
    plot_area_sqm: float | None = None
    plot_area_with_tp: float | None = None
    road_width_m: float | None = None
    num_flats: int | None = None
    num_commercial: int | None = None
    residential_area_sqft: float | None = None
    commercial_area_sqft: float | None = None
    sale_rate: float | None = None
    society_age: int | None = None
    existing_bua_sqft: float | None = None
    pfa_sqft: float | None = None
    ocr_data: dict | None = None
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SocietyListItem(BaseModel):
    id: UUID
    name: str
    address: str
    registration_number: str | None = None
    poc_name: str | None = None
    cts_no: str | None = None
    fp_no: str | None = None
    cts_validated: str | None = None
    ward: str | None = None
    village: str | None = None
    status: str
    num_flats: int | None = None
    plot_area_sqm: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Society Reports --------------------------------------------------------


class ReportCreate(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    report_type: str = Field(default="feasibility", max_length=100)


class ReportResponse(BaseModel):
    id: UUID
    society_id: UUID
    title: str
    report_type: str
    file_url: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Society Tenders ---------------------------------------------------------


class TenderCreate(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    requirements: str | None = Field(default=None, max_length=5000)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    deadline: datetime | None = None


class TenderResponse(BaseModel):
    id: UUID
    society_id: UUID
    title: str
    description: str | None = None
    requirements: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    deadline: datetime | None = None
    status: str
    awarded_to: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
