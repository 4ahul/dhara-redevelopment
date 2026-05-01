from pydantic import BaseModel, Field


class PlotData(BaseModel):
    cts_no: str
    village: str
    ward: str
    plot_area_sqm: float = 0.0


class SiteAnalysisResult(BaseModel):
    lat: float
    lng: float
    formatted_address: str
    area_type: str
    nearby_landmarks: list[str] = Field(default_factory=list)
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
    rr_open_land_sqm: float
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
    existing_residential_area_sqft: float = 0.0
    existing_commercial_area_sqft: float = 0.0
    num_flats: int = 0
    num_commercial: int = 0
    sale_rate_per_sqft: float = 0.0
