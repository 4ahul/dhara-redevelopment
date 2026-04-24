"""
Feasibility Analyze Request/Response Schemas
"""


from pydantic import BaseModel, Field


class FeasibilityAnalyzeRequest(BaseModel):
    """Request for full feasibility analysis - orchestrates all microservices."""
    society_name: str | None = Field(default=None, max_length=255, description="Name of the society")
    address: str = Field(min_length=5, max_length=2000, description="Society address")
    cts_no: str | None = Field(default=None, max_length=100, description="CTS number (1991 scheme)")
    fp_no: str | None = Field(default=None, max_length=100, description="FP number (2034 scheme)")
    ward: str | None = Field(default=None, max_length=20, description="MCGM ward code")
    village: str | None = Field(default=None, max_length=255, description="Village name")
    tps_name: str | None = Field(default=None, max_length=255, description="TPS scheme name (e.g. TPS-VI Vileparle)")
    use_fp_scheme: bool = Field(default=False, description="Use FP scheme (2034) instead of CTS (1991)")
    # Optional override fields passed through to report generator
    scheme: str | None = Field(default="33(7)(B)", max_length=50, description="Regulation scheme for report template")
    redevelopment_type: str | None = Field(default="CLUBBING", description="CLUBBING or INSITU")
    num_flats: int | None = Field(default=None, ge=0)
    num_commercial: int | None = Field(default=None, ge=0)
    society_age: int | None = Field(default=None, ge=0)
    existing_bua_sqft: float | None = Field(default=None, ge=0)
    plot_area_sqm: float | None = Field(default=None, ge=0)
    road_width_m: float | None = Field(default=None, ge=0)
    manual_inputs: dict | None = Field(default=None, description="Manual overrides for yellow cells")
    financial: dict | None = Field(default=None, description="Financial inputs override")


class FeasibilityAnalyzeResponse(BaseModel):
    """Response for feasibility analysis."""
    job_id: str
    status: str = "processing"
    round1_results: dict | None = None
    round2_results: dict | None = None
    report_generated: bool | None = None
    report_error: str | None = None


