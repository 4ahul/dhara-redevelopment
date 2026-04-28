from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class RedevelopmentType(StrEnum):
    CLUBBING = "CLUBBING"
    INSITU = "INSITU"


class ReportRequest(BaseModel):
    """All data required to generate the feasibility report."""

    # Scheme selection - determines which template to use
    scheme: str | None = None

    # Cover info
    society_name: str
    ref_no: str | None = None
    property_desc: str | None = None
    location: str | None = None
    ward: str | None = None
    zone: str | None = None
    plot_area_sqm: float | None = None
    road_width_m: float | None = None
    num_flats: int = 0
    num_commercial: int = 0

    # Unit breakdowns
    commercial_units: list[dict] = []
    residential_units: list[dict] = []

    # FSI data per scheme
    fsi: dict = {}
    bua: dict = {}

    # Financial per scheme
    financial: dict = {}

    # Additional area entitlement
    additional_entitlement: dict = {}

    # All service outputs (maps to yellow cells in template)
    site_analysis: dict = {}
    height: dict = {}
    ready_reckoner: dict = {}
    premium: dict = {}
    zone_regulations: dict = {}
    dp_report: dict = {}
    mcgm_property: dict = {}  # From get_mcgm_property service
    regulatory_sources: list[dict] = []

    # Manual inputs for yellow cells not covered by microservices
    manual_inputs: dict = {}

    # LLM narrative
    llm_analysis: str | None = None


class TemplateReportRequest(BaseModel):
    """Request for template-based feasibility report generation.

    This is the new format that passes all microservice data to generate
    a report using Excel templates.
    """

    # Scheme selection - determines which template to use (REQUIRED)
    scheme: str
    # Redevelopment type — CLUBBING (default) or INSITU
    redevelopment_type: RedevelopmentType = RedevelopmentType.CLUBBING

    # Cover info
    society_name: str
    ref_no: str | None = None
    property_desc: str | None = None
    location: str | None = None
    ward: str | None = None
    zone: str | None = None
    plot_area_sqm: float | None = None
    road_width_m: float | None = None
    num_flats: int = 0
    num_commercial: int = 0

    # Society existing areas (map directly to yellow cells in Details sheet)
    existing_commercial_carpet_sqft: float | None = None  # → Details!O53
    existing_residential_carpet_sqft: float | None = None  # → Details!Q53
    sale_rate_per_sqft: float | None = None  # → P&L!D28 (fallback)

    # Full microservice outputs - these map to yellow cells
    site_analysis: dict | None = {}
    height: dict | None = {}
    premium: dict | None = {}
    dp_report: dict | None = {}
    mcgm_property: dict | None = {}
    zone_regulations: dict | None = {}
    ready_reckoner: dict | None = {}

    # Financial data
    financial: dict | None = {}
    fsi: dict | None = {}
    bua: dict | None = {}

    # Regulatory citations from RAG service
    regulatory_sources: list[dict] = []

    # Manual inputs for yellow cells (values not from microservices)
    manual_inputs: dict | None = {}

    # LLM narrative
    llm_analysis: str | None = None


class TemplateFieldSchema(BaseModel):
    """Schema for a yellow input field in the template."""

    sheet: str
    cell: str
    label: str
    current_value: Any | None = None


class TemplateFieldsResponse(BaseModel):
    """Response with all template fields for a scheme."""

    scheme: str
    template_file: str
    sheets: list[str]
    fields: list[TemplateFieldSchema]


class TemplateApplyRequest(BaseModel):
    """Request to apply values to template."""

    scheme: str
    values: dict[str, Any]
