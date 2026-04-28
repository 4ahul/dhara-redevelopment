from pydantic import BaseModel


class SiteAnalysisRequest(BaseModel):
    address: str
    ward: str | None = None
    plot_no: str | None = None


class SiteAnalysisResponse(BaseModel):
    lat: float
    lng: float
    formatted_address: str
    area_type: str
    nearby_landmarks: list[str]
    place_id: str
    zone_inference: str | None = None
    ward: str | None = None
    zone_source: str = "unavailable"
    maps_url: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    step: int
