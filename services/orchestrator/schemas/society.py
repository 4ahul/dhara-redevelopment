from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..models.enums import SocietyStatus

# ---------------------------------------------------------------------------
# Shared Pydantic config: accept both camelCase (FE) and snake_case (BE),
# serialize output as camelCase for the frontend.
# ---------------------------------------------------------------------------
_CAMEL_CFG = {
    "from_attributes": True,
    "populate_by_name": True,
    "alias_generator": lambda s: "".join(
        word.capitalize() if i else word for i, word in enumerate(s.split("_"))
    ),
}


# --- Society Create ----------------------------------------------------------


class SocietyCreate(BaseModel):
    """Create a new society."""

    name: str = Field(min_length=2, max_length=500)
    address: str = Field(min_length=5, max_length=2000, alias="location")
    onboarded_date: datetime | None = Field(default=None, alias="onboardedDate")
    initial_status: SocietyStatus | None = Field(default=SocietyStatus.NEW, alias="initialStatus")
    notes: str | None = None
    point_of_contact: list[dict] | None = Field(
        default=None,
        alias="pointOfContact",
        description="Array of {contactPerson, contactMail, contactPhone}",
    )

    model_config = {"populate_by_name": True}

    @field_validator("onboarded_date", mode="before")
    @classmethod
    def _parse_unix_ms(cls, v: Any) -> Any:
        """FE may send onboardedDate as unix milliseconds."""
        if isinstance(v, (int, float)) and v > 1_000_000_000_000:
            return datetime.fromtimestamp(v / 1000, tz=UTC).replace(tzinfo=None)
        return v

    @field_validator("onboarded_date")
    @classmethod
    def _ensure_naive(cls, v: datetime | None) -> datetime | None:
        if v and v.tzinfo:
            return v.astimezone(UTC).replace(tzinfo=None)
        return v


# --- Society Update ----------------------------------------------------------


class SocietyUpdate(BaseModel):
    """Partial update."""

    name: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=2000, alias="location")
    onboarded_date: datetime | None = Field(default=None, alias="onboardedDate")
    notes: str | None = None
    status: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("onboarded_date", mode="before")
    @classmethod
    def _parse_unix_ms(cls, v: Any) -> Any:
        if isinstance(v, (int, float)) and v > 1_000_000_000_000:
            return datetime.fromtimestamp(v / 1000, tz=UTC).replace(tzinfo=None)
        return v

    @field_validator("onboarded_date")
    @classmethod
    def _ensure_naive(cls, v: datetime | None) -> datetime | None:
        if v and v.tzinfo:
            return v.astimezone(UTC).replace(tzinfo=None)
        return v


# --- Society Response (full detail) ------------------------------------------


class SocietyResponse(BaseModel):
    """Full society detail -- serialized as camelCase for FE."""

    id: UUID
    name: str
    address: str = Field(serialization_alias="location")
    poc_name: str | None = Field(default=None, serialization_alias="contactPerson")
    poc_phone: str | None = Field(default=None, serialization_alias="contactPhone")
    poc_email: str | None = Field(default=None, serialization_alias="contactEmail")
    onboarded_date: datetime | None = Field(default=None, serialization_alias="onboardedDate")
    notes: str | None = None
    status: str

    reports: int = Field(default=0, description="Count of reports for this society")
    tenders: int = Field(default=0, description="Count of tenders for this society")
    created_by: UUID = Field(serialization_alias="createdBy")

    @field_validator("reports", "tenders", mode="before")
    @classmethod
    def _convert_rel_to_count(cls, v: Any) -> int:
        if isinstance(v, (list, tuple)) or hasattr(v, "__len__"):
            return len(v)
        return v or 0

    created_at: datetime = Field(serialization_alias="registeredOn")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


# --- Society List Item (abbreviated) -----------------------------------------


class SocietyListItem(BaseModel):
    """Abbreviated society for list views -- serialized as camelCase."""

    id: UUID
    name: str
    address: str = Field(serialization_alias="location")
    poc_name: str | None = Field(default=None, serialization_alias="contactPerson")
    poc_phone: str | None = Field(default=None, serialization_alias="contactPhone")
    status: str
    notes: str | None = None

    reports: int = Field(default=0, description="Count of reports")
    tenders: int = Field(default=0, description="Count of tenders")

    @field_validator("reports", "tenders", mode="before")
    @classmethod
    def _convert_rel_to_count(cls, v: Any) -> int:
        if isinstance(v, (list, tuple)) or hasattr(v, "__len__"):
            return len(v)
        return v or 0

    created_at: datetime = Field(serialization_alias="registeredOn")

    model_config = {"from_attributes": True, "populate_by_name": True}


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
    """Create tender -- accepts FE camelCase via aliases."""

    title: str = Field(min_length=2, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    requirements: str | None = Field(default=None, max_length=5000, alias="scope")
    budget_min: float | None = Field(default=None, ge=0, alias="budgetMin")
    budget_max: float | None = Field(default=None, ge=0, alias="budgetMax")
    estimated_value: str | None = Field(default=None, alias="estimatedValue")
    deadline: datetime | None = None

    model_config = {"populate_by_name": True}

    @field_validator("deadline")
    @classmethod
    def _ensure_naive(cls, v: datetime | None) -> datetime | None:
        if v and v.tzinfo:
            return v.astimezone(UTC).replace(tzinfo=None)
        return v


class TenderResponse(BaseModel):
    """Tender response -- serialized as camelCase for FE."""

    id: UUID
    society_id: UUID = Field(serialization_alias="societyId")
    title: str
    description: str | None = None
    requirements: str | None = Field(default=None, serialization_alias="scope")
    budget_min: float | None = Field(default=None, serialization_alias="budgetMin")
    budget_max: float | None = Field(default=None, serialization_alias="budgetMax")
    estimated_value: str | None = Field(default=None, serialization_alias="estimatedValue")
    deadline: datetime | None = None
    status: str
    awarded_to: UUID | None = Field(default=None, serialization_alias="awardedTo")
    responses_count: int = Field(default=0, serialization_alias="responsesCount")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


# --- Feasibility Reports ----------------------------------------------------


class FeasibilityReportCreate(BaseModel):
    """Create feasibility report -- accepts FE camelCase via aliases."""

    society_id: UUID = Field(alias="societyId")
    title: str | None = Field(default="Feasibility Report", max_length=500)
    # Land identification
    land_identifier_type: str | None = Field(default=None, alias="landIdentifierType")
    land_identifier_value: str | None = Field(default=None, alias="landIdentifierValue")
    cts_no: str | None = Field(default=None, max_length=100, alias="ctsNo")
    fp_no: str | None = Field(default=None, max_length=100, alias="fpNo")
    # Tenement info
    tenement_mode: str | None = Field(default=None, alias="tenementMode")
    num_flats: int | None = Field(default=None, ge=0, alias="numberOfTenements")
    num_commercial: int | None = Field(default=None, ge=0, alias="numberOfCommercialShops")
    # Financial inputs
    basement_required: str | None = Field(default=None, alias="basementRequired")
    corpus_commercial: float | None = Field(default=None, ge=0, alias="corpusCommercial")
    corpus_residential: float | None = Field(default=None, ge=0, alias="corpusResidential")
    bank_guarantee_commercial: float | None = Field(
        default=None, ge=0, alias="bankGuaranteeCommercial"
    )
    bank_guarantee_residential: float | None = Field(
        default=None, ge=0, alias="bankGuaranteeResidential"
    )
    sale_commercial_bua_sqft: float | None = Field(
        default=None, ge=0, alias="saleCommercialMunBuaSqFt"
    )
    const_rate_commercial: float | None = Field(
        default=None, ge=0, alias="commercialAreaCostPerSqFt"
    )
    const_rate_residential: float | None = Field(
        default=None, ge=0, alias="residentialAreaCostPerSqFt"
    )
    const_rate_podium: float | None = Field(default=None, ge=0, alias="podiumParkingCostPerSqFt")
    const_rate_basement: float | None = Field(default=None, ge=0, alias="basementCostPerSqFt")
    cost_79a_acquisition: float | None = Field(default=None, ge=0, alias="costAcquisition79a")
    # Commercial floor breakdowns (FE sends nested saleAreaBreakup, we accept flat)
    commercial_gf_area: float | None = Field(default=None, ge=0)
    sale_rate_commercial_gf: float | None = Field(default=None, ge=0)
    commercial_1f_area: float | None = Field(default=None, ge=0)
    sale_rate_commercial_1f: float | None = Field(default=None, ge=0)
    commercial_2f_area: float | None = Field(default=None, ge=0)
    sale_rate_commercial_2f: float | None = Field(default=None, ge=0)
    commercial_other_area: float | None = Field(default=None, ge=0)
    sale_rate_commercial_other: float | None = Field(default=None, ge=0)
    sale_rate_residential: float | None = Field(
        default=None, ge=0, alias="salableResidentialRatePerSqFt"
    )
    parking_price_per_unit: float | None = Field(default=None, ge=0, alias="carsToSellRatePerCar")
    # Nested sale area breakup (FE format) -- flattened in service layer
    sale_area_breakup: dict | None = Field(default=None, alias="saleAreaBreakup")

    model_config = {"populate_by_name": True}

    @field_validator("basement_required", mode="before")
    @classmethod
    def _coerce_basement(cls, v: Any) -> Any:
        """FE sends 'yes'/'no' string; coerce to keep as string for now."""
        if isinstance(v, bool):
            return "yes" if v else "no"
        return v


class FeasibilityReportUpdate(BaseModel):
    """Partial update -- accepts FE camelCase."""

    title: str | None = Field(default=None, max_length=500)
    status: str | None = None
    llm_analysis: str | None = Field(default=None, alias="aiSummary")
    feasibility: str | None = None
    fsi: float | None = None
    estimated_value: str | None = Field(default=None, alias="estimatedValue")
    plot_area: float | None = Field(default=None, alias="plotArea")
    existing_units: int | None = Field(default=None, alias="existingUnits")
    proposed_units: int | None = Field(default=None, alias="proposedUnits")
    structural_grade: str | None = Field(default=None, alias="structuralGrade")
    completion_days: int | None = Field(default=None, alias="completionDays")

    model_config = {"populate_by_name": True}


class FeasibilityReportResponse(BaseModel):
    """Report response -- serialized as camelCase for FE."""

    id: UUID
    society_id: UUID = Field(serialization_alias="societyId")
    user_id: UUID = Field(serialization_alias="userId")
    title: str
    report_path: str | None = Field(default=None, serialization_alias="reportPath")
    file_url: str | None = Field(default=None, serialization_alias="fileUrl")
    status: str
    feasibility: str | None = Field(default="pending")
    fsi: float | None = None
    estimated_value: str | None = Field(default=None, serialization_alias="estimatedValue")
    plot_area: float | None = Field(default=None, serialization_alias="plotArea")
    existing_units: int | None = Field(default=None, serialization_alias="existingUnits")
    proposed_units: int | None = Field(default=None, serialization_alias="proposedUnits")
    structural_grade: str | None = Field(default=None, serialization_alias="structuralGrade")
    completion_days: int | None = Field(default=None, serialization_alias="completionDays")
    llm_analysis: str | None = Field(default=None, serialization_alias="aiSummary")
    input_data: dict | None = Field(default=None, serialization_alias="inputData")
    output_data: dict | None = Field(default=None, serialization_alias="outputData")
    error_message: str | None = Field(default=None, serialization_alias="errorMessage")

    # ── Summary Snapshot Fields ──────────────────────────────────────────────
    ward: str | None = None
    village: str | None = None
    cts_no: str | None = Field(default=None, serialization_alias="ctsNo")
    fp_no: str | None = Field(default=None, serialization_alias="fpNo")

    # Computed: populated in router from ORM relationship
    society: str | None = Field(default=None, description="Society name")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}
