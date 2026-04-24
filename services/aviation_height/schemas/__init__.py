from pydantic import BaseModel
from typing import Optional, Union


class HeightRequest(BaseModel):
    lat: float
    lng: float
    site_elevation: Optional[float] = None


class HeightResponse(BaseModel):
    lat: float
    lng: float
    site_elevation: float
    elevation_source: Optional[str] = None
    max_height_m: Optional[float] = None
    max_floors: Optional[int] = None
    restriction_reason: str
    nocas_reference: Optional[str] = None
    aai_zone: Optional[str] = None
    rl_datum_m: Optional[float] = None
    is_real_data: bool = True
    data_source: str = "aai_nocas"
    error: Optional[str] = None

