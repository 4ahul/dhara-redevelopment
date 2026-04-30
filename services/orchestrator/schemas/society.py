from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared Pydantic config: accept both camelCase (FE) and snake_case (BE),
# serialize output as camelCase for the frontend.
# ---------------------------------------------------------------------------
_CAMEL_CFG = {
    'from_attributes': True,
    'populate_by_name': True,
    'alias_generator': lambda s: ''.join(
        word.capitalize() if i else word
        for i, word in enumerate(s.split('_'))
    ),
}


# --- Society Create ----------------------------------------------------------


class SocietyCreate(BaseModel):
    """Create a new society -- accepts FE camelCase OR BE snake_case field names."""
    name: str = Field(min_length=2, max_length=500)
    address: str = Field(min_length=5, max_length=2000, alias='location')
    registration_number: str | None = Field(default=None, max_length=100, alias='registrationNumber')
    num_flats: int | None = Field(default=None, ge=0, alias='totalFlats')
    year_built: int | None = Field(default=None, alias='yearBuilt')
    poc_name: str | None = Field(default=None, max_length=255, alias='contactPerson')
    poc_phone: str | None = Field(default=None, max_length=50, alias='contactPhone')
    poc_email: str | None = Field(default=None, max_length=255, alias='contactEmail')
    onboarded_date: datetime | None = Field(default=None, alias='onboardedDate')
    initial_status: str | None = Field(default='new', alias='initialStatus')
    notes: str | None = None
    point_of_contact: list[dict] | None = Field(default=None, alias='pointOfContact',
        description='Array of {contactPerson, contactMail, contactPhone}')
    # BE-native fields (no alias needed)
    ward: str | None = Field(default=None, max_length=20)
    village: str | None = Field(default=None, max_length=255)
    taluka: str | None = Field(default=None, max_length=255)
    district: str | None = Field(default=None, max_length=255)
    plot_area_sqm: float | None = Field(default=None, ge=0)
    plot_area_with_tp: float | None = Field(default=None, ge=0)
    road_width_m: float | None = Field(default=None, ge=0)
    num_commercial: int | None = Field(default=None, ge=0)
    residential_area_sqft: float | None = Field(default=None, ge=0)
    commercial_area_sqft: float | None = Field(default=None, ge=0)
    sale_rate: float | None = Field(default=None, ge=0)
    society_age: int | None = Field(default=None, ge=0)
    existing_bua_sqft: float | None = Field(default=None, ge=0)
    pfa_sqft: float | None = Field(default=None, ge=0)
    ocr_data: dict | None = Field(default=None)

    model_config = {'populate_by_name': True}

    @field_validator('onboarded_date', mode='before')
    @classmethod
    def _parse_unix_ms(cls, v: Any) -> Any:
        """FE may send onboardedDate as unix milliseconds."""
        if isinstance(v, (int, float)) and v > 1_000_000_000_000:
            return datetime.utcfromtimestamp(v / 1000)
        return v


# --- Society Update ----------------------------------------------------------


class SocietyUpdate(BaseModel):
    """Partial update -- accepts both FE and BE field names."""
    name: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=2000, alias='location')
    registration_number: str | None = Field(default=None, max_length=100, alias='registrationNumber')
    num_flats: int | None = Field(default=None, ge=0, alias='totalFlats')
    year_built: int | None = Field(default=None, alias='yearBuilt')
    poc_name: str | None = Field(default=None, max_length=255, alias='contactPerson')
    poc_phone: str | None = Field(default=None, max_length=50, alias='contactPhone')
    poc_email: str | None = Field(default=None, max_length=255, alias='contactEmail')
    onboarded_date: datetime | None = Field(default=None, alias='onboardedDate')
    notes: str | None = None
    is_manual_process: bool | None = Field(default=None, alias='isManualProcess')
    status: str | None = None
    # BE-native fields
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
    num_commercial: int | None = Field(default=None, ge=0)
    residential_area_sqft: float | None = Field(default=None, ge=0)
    commercial_area_sqft: float | None = Field(default=None, ge=0)
    sale_rate: float | None = Field(default=None, ge=0)

    model_config = {'populate_by_name': True}

    @field_validator('onboarded_date', mode='before')
    @classmethod
    def _parse_unix_ms(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and v > 1_000_000_000_000:
            return datetime.utcfromtimestamp(v / 1000)
        return v


# --- Society Response (full detail) ------------------------------------------


class SocietyResponse(BaseModel):
    """Full society detail -- serialized as camelCase for FE."""
    id: UUID
    name: str
    address: str = Field(serialization_alias='location')
    registration_number: str | None = Field(default=None, serialization_alias='registrationNumber')
    num_flats: int | None = Field(default=None, serialization_alias='totalFlats')
    year_built: int | None = Field(default=None, serialization_alias='yearBuilt')
    poc_name: str | None = Field(default=None, serialization_alias='contactPerson')
    poc_phone: str | None = Field(default=None, serialization_alias='contactPhone')
    poc_email: str | None = Field(default=None, serialization_alias='contactEmail')
    onboarded_date: datetime | None = Field(default=None, serialization_alias='onboardedDate')
    notes: str | None = None
    is_manual_process: bool = Field(default=False, serialization_alias='isManualProcess')
    cts_no: str | None = Field(default=None, serialization_alias='ctsNo')
    fp_no: str | None = Field(default=None, serialization_alias='fpNo')
    tps_name: str | None = Field(default=None, serialization_alias='tpsName')
    cts_validated: str | None = Field(default=None, serialization_alias='ctsValidated')
    ward: str | None = None
    village: str | None = None
    taluka: str | None = None
    district: str | None = None
    plot_area_sqm: float | None = Field(default=None, serialization_alias='plotAreaSqm')
    plot_area_with_tp: float | None = Field(default=None, serialization_alias='plotAreaWithTp')
    road_width_m: float | None = Field(default=None, serialization_alias='roadWidthM')
    num_commercial: int | None = Field(default=None, serialization_alias='numCommercial')
    residential_area_sqft: float | None = Field(default=None, serialization_alias='residentialAreaSqft')
    commercial_area_sqft: float | None = Field(default=None, serialization_alias='commercialAreaSqft')
    sale_rate: float | None = Field(default=None, serialization_alias='saleRate')
    society_age: int | None = Field(default=None, serialization_alias='societyAge')
    existing_bua_sqft: float | None = Field(default=None, serialization_alias='existingBuaSqft')
    pfa_sqft: float | None = Field(default=None, serialization_alias='pfaSqft')
    ocr_data: dict | None = Field(default=None, serialization_alias='ocrData')
    lat: float | None = None
    lng: float | None = None
    status: str
    reports: int = Field(default=0, description='Count of reports for this society')
    tenders: int = Field(default=0, description='Count of tenders for this society')
    created_by: UUID = Field(serialization_alias='createdBy')
    created_at: datetime = Field(serialization_alias='registeredOn')
    updated_at: datetime = Field(serialization_alias='updatedAt')

    model_config = {'from_attributes': True, 'populate_by_name': True}


# --- Society List Item (abbreviated) -----------------------------------------


class SocietyListItem(BaseModel):
    """Abbreviated society for list views -- serialized as camelCase."""
    id: UUID
    name: str
    address: str = Field(serialization_alias='location')
    registration_number: str | None = Field(default=None, serialization_alias='registrationNumber')
    num_flats: int | None = Field(default=None, serialization_alias='totalFlats')
    year_built: int | None = Field(default=None, serialization_alias='yearBuilt')
    poc_name: str | None = Field(default=None, serialization_alias='contactPerson')
    poc_phone: str | None = Field(default=None, serialization_alias='contactPhone')
    cts_no: str | None = Field(default=None, serialization_alias='ctsNo')
    fp_no: str | None = Field(default=None, serialization_alias='fpNo')
    cts_validated: str | None = Field(default=None, serialization_alias='ctsValidated')
    ward: str | None = None
    village: str | None = None
    status: str
    plot_area_sqm: float | None = Field(default=None, serialization_alias='plotAreaSqm')
    notes: str | None = None
    reports: int = Field(default=0, description='Count of reports')
    tenders: int = Field(default=0, description='Count of tenders')
    created_at: datetime = Field(serialization_alias='registeredOn')

    model_config = {'from_attributes': True, 'populate_by_name': True}


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
    cts_no: str | None = Field(default=None, max_length=100)
    fp_no: str | None = Field(default=None, max_length=100)
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
