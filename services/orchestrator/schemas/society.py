from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# --- Society -----------------------------------------------------------------


class SocietyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=500)
    address: str = Field(min_length=5, max_length=2000)
    poc_name: str | None = Field(default=None, max_length=255)
    poc_phone: str | None = Field(default=None, max_length=50)
    poc_email: str | None = Field(default=None, max_length=255)
    onboarded_date: datetime | None = None
    notes: str | None = None
    ward: str | None = Field(default=None, max_length=20, description='Auto-resolved from address')
    village: str | None = Field(default=None, max_length=255, description='Auto-resolved from address')
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
    society_age: int | None = Field(default=None, ge=0, description='Year OC was issued or years since')
    existing_bua_sqft: float | None = Field(default=None, ge=0, description='Existing Built Up Area in sq ft')
    pfa_sqft: float | None = Field(default=None, ge=0, description='PFA from original OC in sq ft')
    ocr_data: dict | None = Field(default=None, description='Raw OCR output from document scan')


class SocietyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=2000)
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


class SocietyResponse(BaseModel):
    id: UUID
    name: str
    address: str
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
    lat: float | None = None
    lng: float | None = None
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class SocietyListItem(BaseModel):
    id: UUID
    name: str
    address: str
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

    model_config = {'from_attributes': True}


# --- Society Reports --------------------------------------------------------


class ReportCreate(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    report_type: str = Field(default='feasibility', max_length=100)


class ReportResponse(BaseModel):
    id: UUID
    society_id: UUID
    title: str
    report_type: str
    file_url: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


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

    model_config = {'from_attributes': True}


# --- Feasibility Reports ----------------------------------------------------


class FeasibilityReportCreate(BaseModel):
    society_id: UUID
    title: str | None = Field(default='Feasibility Report', max_length=500)
    cts_no: str | None = Field(default=None, max_length=100, description='CTS/CS number (1991 scheme)')
    fp_no: str | None = Field(default=None, max_length=100, description='Final Plot number (2034 scheme)')
    num_flats: int | None = Field(default=None, ge=0)
    num_commercial: int | None = Field(default=None, ge=0)
    basement_required: bool | None = None
    corpus_commercial: float | None = Field(default=None, ge=0)
    corpus_residential: float | None = Field(default=None, ge=0)
    sale_commercial_bua_sqft: float | None = Field(default=None, ge=0)
    const_rate_commercial: float | None = Field(default=None, ge=0)
    const_rate_residential: float | None = Field(default=None, ge=0)
    const_rate_podium: float | None = Field(default=None, ge=0)
    const_rate_basement: float | None = Field(default=None, ge=0)
    cost_79a_acquisition: float | None = Field(default=None, ge=0)
    commercial_gf_area: float | None = Field(default=None, ge=0)
    sale_rate_commercial_gf: float | None = Field(default=None, ge=0)
    commercial_1f_area: float | None = Field(default=None, ge=0)
    sale_rate_commercial_1f: float | None = Field(default=None, ge=0)
    commercial_2f_area: float | None = Field(default=None, ge=0)
    sale_rate_commercial_2f: float | None = Field(default=None, ge=0)
    commercial_other_area: float | None = Field(default=None, ge=0)
    sale_rate_commercial_other: float | None = Field(default=None, ge=0)
    sale_rate_residential: float | None = Field(default=None, ge=0)
    parking_price_per_unit: float | None = Field(default=None, ge=0)


class FeasibilityReportUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    status: str | None = None
    llm_analysis: str | None = None


class FeasibilityReportResponse(BaseModel):
    id: UUID
    society_id: UUID
    user_id: UUID
    title: str
    report_path: str | None = None
    file_url: str | None = None
    status: str
    input_data: dict | None = None
    output_data: dict | None = None
    llm_analysis: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


