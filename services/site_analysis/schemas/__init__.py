from pydantic import BaseModel
from typing import Optional


class SiteAnalysisRequest(BaseModel):
    address: str
    ward: Optional[str] = None
    plot_no: Optional[str] = None


class SiteAnalysisResponse(BaseModel):
    lat: float
    lng: float
    formatted_address: str
    area_type: str
    nearby_landmarks: list[str]
    place_id: str
    zone_inference: Optional[str] = None
    ward: Optional[str] = None
    zone_source: str = "unavailable"
    maps_url: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    step: int

