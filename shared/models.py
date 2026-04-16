from pydantic import BaseModel
from typing import Optional


class PlotData(BaseModel):
    cts_no: str
    village: str
    ward: str
    plot_area_sqm: Optional[float] = None
    road_width_m: Optional[float] = None
    zone: Optional[str] = None
    crz_category: Optional[str] = None
    dp_remarks: Optional[str] = None
    address: Optional[str] = None


class SiteAnalysisResult(BaseModel):
    lat: float
    lng: float
    formatted_address: str
    area_type: str  # residential / commercial / mixed
    nearby_landmarks: list[str]
    place_id: str
    zone_inference: str


class HeightResult(BaseModel):
    lat: float
    lng: float
    max_height_m: float
    max_floors: int
    restriction_reason: str
    nocas_reference: str


class ReadyReckoner(BaseModel):
    ward: str
    zone: str
    rr_open_land_sqm: float  # INR per sqm
    rr_residential_sqm: float
    rr_commercial_sqm: float
    rr_construction_cost_sqm: float
    year: int


class PremiumData(BaseModel):
    plot_area_sqm: float
    fsi_premium_amount: float
    tdr_cost: float
    fungible_premium: float
    open_space_deficiency: float
    total_govt_charges: float


class FeasibilityInput(BaseModel):
    plot_data: PlotData
    site_analysis: SiteAnalysisResult
    height_result: HeightResult
    ready_reckoner: ReadyReckoner
    premium_data: PremiumData
    society_name: str
    existing_residential_area_sqft: float
    existing_commercial_area_sqft: float
    num_flats: int
    num_commercial: int
    sale_rate_per_sqft: float = 60000.0
    llm_analysis: Optional[str] = None
