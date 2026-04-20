"""
Dhara AI — Society Schemas
Request/Response models for society, reports, and tenders endpoints.
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# ─── Society ─────────────────────────────────────────────────────────────────


class SocietyCreate(BaseModel):
    """Create a new society record."""

    name: str = Field(min_length=2, max_length=500)
    address: str = Field(min_length=5, max_length=2000)
    cts_no: Optional[str] = Field(default=None, max_length=100)
    # ward, village, taluka, district are now auto-resolved from address via web search
    # Kept as optional for manual override
    ward: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Auto-resolved from address if not provided",
    )
    village: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Auto-resolved from address if not provided",
    )
    taluka: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Auto-resolved from address if not provided",
    )
    district: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Auto-resolved from address if not provided",
    )
    plot_area_sqm: Optional[float] = Field(default=None, ge=0)
    plot_area_with_tp: Optional[float] = Field(default=None, ge=0)
    road_width_m: Optional[float] = Field(default=None, ge=0)
    num_flats: Optional[int] = Field(default=None, ge=0)
    num_commercial: Optional[int] = Field(default=None, ge=0)
    residential_area_sqft: Optional[float] = Field(default=None, ge=0)
    commercial_area_sqft: Optional[float] = Field(default=None, ge=0)
    sale_rate: Optional[float] = Field(default=None, ge=0)


class SocietyUpdate(BaseModel):
    """Partial update for society details."""

    name: Optional[str] = Field(default=None, max_length=500)
    address: Optional[str] = Field(default=None, max_length=2000)
    cts_no: Optional[str] = Field(default=None, max_length=100)
    ward: Optional[str] = Field(default=None, max_length=20)
    village: Optional[str] = Field(default=None, max_length=255)
    taluka: Optional[str] = Field(default=None, max_length=255)
    district: Optional[str] = Field(default=None, max_length=255)
    plot_area_sqm: Optional[float] = Field(default=None, ge=0)
    plot_area_with_tp: Optional[float] = Field(default=None, ge=0)
    road_width_m: Optional[float] = Field(default=None, ge=0)
    num_flats: Optional[int] = Field(default=None, ge=0)
    num_commercial: Optional[int] = Field(default=None, ge=0)
    residential_area_sqft: Optional[float] = Field(default=None, ge=0)
    commercial_area_sqft: Optional[float] = Field(default=None, ge=0)
    sale_rate: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None


class SocietyResponse(BaseModel):
    """Full society detail response."""

    id: UUID
    name: str
    address: str
    cts_no: Optional[str] = None
    ward: Optional[str] = None
    village: Optional[str] = None
    taluka: Optional[str] = None
    district: Optional[str] = None
    plot_area_sqm: Optional[float] = None
    plot_area_with_tp: Optional[float] = None
    road_width_m: Optional[float] = None
    num_flats: Optional[int] = None
    num_commercial: Optional[int] = None
    residential_area_sqft: Optional[float] = None
    commercial_area_sqft: Optional[float] = None
    sale_rate: Optional[float] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SocietyListItem(BaseModel):
    """Abbreviated society item for list views."""

    id: UUID
    name: str
    address: str
    ward: Optional[str] = None
    status: str
    num_flats: Optional[int] = None
    plot_area_sqm: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Society Reports ────────────────────────────────────────────────────────


class ReportCreate(BaseModel):
    """Create a society report."""

    title: str = Field(min_length=2, max_length=500)
    report_type: str = Field(default="feasibility", max_length=100)


class ReportResponse(BaseModel):
    """Society report response."""

    id: UUID
    society_id: UUID
    title: str
    report_type: str
    file_url: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Society Tenders ─────────────────────────────────────────────────────────


class TenderCreate(BaseModel):
    """Create a tender for a society."""

    title: str = Field(min_length=2, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    requirements: Optional[str] = Field(default=None, max_length=5000)
    budget_min: Optional[float] = Field(default=None, ge=0)
    budget_max: Optional[float] = Field(default=None, ge=0)
    deadline: Optional[datetime] = None


class TenderResponse(BaseModel):
    """Tender response."""

    id: UUID
    society_id: UUID
    title: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    deadline: Optional[datetime] = None
    status: str
    awarded_to: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Feasibility Reports ────────────────────────────────────────────────────


class FeasibilityReportCreate(BaseModel):
    """Trigger a feasibility report generation."""

    society_id: UUID
    title: Optional[str] = Field(default="Feasibility Report", max_length=500)


class FeasibilityReportUpdate(BaseModel):
    """Partial update on a feasibility report."""

    title: Optional[str] = Field(default=None, max_length=500)
    status: Optional[str] = None
    llm_analysis: Optional[str] = None


class FeasibilityReportResponse(BaseModel):
    """Feasibility report response."""

    id: UUID
    society_id: UUID
    user_id: UUID
    title: str
    report_path: Optional[str] = None
    file_url: Optional[str] = None
    status: str
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    llm_analysis: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
