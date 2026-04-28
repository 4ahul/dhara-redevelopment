"""
Feasibility Analyze Request/Response Schemas
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FeasibilityAnalyzeRequest(BaseModel):
    """Request for full feasibility analysis - orchestrates all microservices."""

    society_name: str | None = Field(
        default=None, max_length=255, description="Name of the society"
    )
    address: str = Field(min_length=5, max_length=2000, description="Society address")
    cts_no: str | None = Field(default=None, max_length=100, description="CTS number (1991 scheme)")
    fp_no: str | None = Field(default=None, max_length=100, description="FP number (2034 scheme)")
    ward: str | None = Field(default=None, max_length=20, description="MCGM ward code")
    village: str | None = Field(default=None, max_length=255, description="Village name")
    tps_name: str | None = Field(
        default=None, max_length=255, description="TPS scheme name (e.g. TPS-VI Vileparle)"
    )
    use_fp_scheme: bool = Field(
        default=False, description="Use FP scheme (2034) instead of CTS (1991)"
    )
    # Optional override fields passed through to report generator
    scheme: str | None = Field(
        default="33(7)(B)", max_length=50, description="Regulation scheme for report template"
    )
    redevelopment_type: str | None = Field(default="CLUBBING", description="CLUBBING or INSITU")
    num_flats: int | None = Field(default=None, ge=0)
    num_commercial: int | None = Field(default=None, ge=0)
    society_age: int | None = Field(default=None, ge=0)
    existing_bua_sqft: float | None = Field(default=None, ge=0)
    plot_area_sqm: float | None = Field(default=None, ge=0)
    road_width_m: float | None = Field(default=None, ge=0)
    manual_inputs: dict | None = Field(
        default=None, description="Manual overrides for yellow cells"
    )
    financial: dict | None = Field(default=None, description="Financial inputs override")
    bankGuranteeCommercial: float | None = Field(
        default=None, ge=0, description="Bank guarantee input commercial (cell gets 15% of this)"
    )
    bankGuranteeResidential: float | None = Field(
        default=None, ge=0, description="Bank guarantee input residential (cell gets 15% of this)"
    )
    costAcquisition79a: float | None = Field(
        default=None, ge=0, description="79A land acquisition cost (SUMMARY 1!I98)"
    )
    salableResidentialRatePerSqFt: float | None = Field(
        default=None, ge=0, description="Residential sale rate per sqft (P&L!D28)"
    )
    carsToSellRatePerCar: float | None = Field(
        default=None, ge=0, description="Parking sale rate per car (P&L!D30)"
    )
    saleAreaBreakup: dict | None = Field(
        default=None,
        description="Commercial floor-wise area+rate: {groundFloor,firstFloor,secondFloor,otherFloors} each {area,rate}",
    )


class FeasibilityAnalyzeResponse(BaseModel):
    """Response for feasibility analysis."""

    job_id: str
    status: str = "processing"
    round1_results: dict | None = None
    round2_results: dict | None = None
    report_generated: bool | None = None
    report_error: str | None = None


# --- Feasibility Reports ----------------------------------------------------


class FeasibilityReportCreate(BaseModel):
    society_id: UUID
    title: str | None = Field(default="Feasibility Report", max_length=500)
    cts_no: str | None = Field(
        default=None, max_length=100, description="CTS/CS number (1991 scheme)"
    )
    fp_no: str | None = Field(
        default=None, max_length=100, description="Final Plot number (2034 scheme)"
    )
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

    model_config = {"from_attributes": True}
