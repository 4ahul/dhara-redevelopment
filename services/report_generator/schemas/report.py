from enum import Enum
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class RedevelopmentType(str, Enum):
    CLUBBING = "CLUBBING"
    INSITU = "INSITU"


class ReportRequest(BaseModel):
    """All data required to generate the feasibility report."""

    # Scheme selection - determines which template to use
    scheme: Optional[str] = None

    # Cover info
    society_name: str
    ref_no: Optional[str] = None
    property_desc: Optional[str] = None
    location: Optional[str] = None
    ward: Optional[str] = None
    zone: Optional[str] = None
    plot_area_sqm: Optional[float] = None
    road_width_m: Optional[float] = None
    num_flats: int = 0
    num_commercial: int = 0

    # Unit breakdowns
    commercial_units: List[Dict] = []
    residential_units: List[Dict] = []

    # FSI data per scheme
    fsi: Dict = {}
    bua: Dict = {}

    # Financial per scheme
    financial: Dict = {}

    # Additional area entitlement
    additional_entitlement: Dict = {}

    # All service outputs (maps to yellow cells in template)
    site_analysis: Dict = {}
    height: Dict = {}
    ready_reckoner: Dict = {}
    premium: Dict = {}
    zone_regulations: Dict = {}
    dp_report: Dict = {}
    mcgm_property: Dict = {}  # From get_mcgm_property service
    regulatory_sources: List[Dict] = []

    # Manual inputs for yellow cells not covered by microservices
    manual_inputs: Dict = {}

    # LLM narrative
    llm_analysis: Optional[str] = None


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
    ref_no: Optional[str] = None
    property_desc: Optional[str] = None
    location: Optional[str] = None
    ward: Optional[str] = None
    zone: Optional[str] = None
    plot_area_sqm: Optional[float] = None
    road_width_m: Optional[float] = None
    num_flats: int = 0
    num_commercial: int = 0

    # Society existing areas (map directly to yellow cells in Details sheet)
    existing_commercial_carpet_sqft: Optional[float] = None   # → Details!O53
    existing_residential_carpet_sqft: Optional[float] = None  # → Details!Q53
    sale_rate_per_sqft: Optional[float] = None                # → P&L!D28 (fallback)

    # Full microservice outputs - these map to yellow cells
    site_analysis: Optional[Dict] = {}
    height: Optional[Dict] = {}
    premium: Optional[Dict] = {}
    dp_report: Optional[Dict] = {}
    mcgm_property: Optional[Dict] = {}
    zone_regulations: Optional[Dict] = {}
    ready_reckoner: Optional[Dict] = {}

    # Financial data
    financial: Optional[Dict] = {}
    fsi: Optional[Dict] = {}
    bua: Optional[Dict] = {}

    # Regulatory citations from RAG service
    regulatory_sources: List[Dict] = []

    # Manual inputs for yellow cells (values not from microservices)
    manual_inputs: Optional[Dict] = {}

    # LLM narrative
    llm_analysis: Optional[str] = None


class TemplateFieldSchema(BaseModel):
    """Schema for a yellow input field in the template."""

    sheet: str
    cell: str
    label: str
    current_value: Optional[Any] = None


class TemplateFieldsResponse(BaseModel):
    """Response with all template fields for a scheme."""

    scheme: str
    template_file: str
    sheets: List[str]
    fields: List[TemplateFieldSchema]


class TemplateApplyRequest(BaseModel):
    """Request to apply values to template."""

    scheme: str
    values: Dict[str, Any]

