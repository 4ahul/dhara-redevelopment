from pydantic import BaseModel
from typing import Optional


class HeightRequest(BaseModel):
    lat: float
    lng: float
    site_elevation: Optional[float] = 0.0


class HeightResponse(BaseModel):
    lat: float
    lng: float
    max_height_m: float
    max_floors: int
    restriction_reason: str
    nocas_reference: str
    aai_zone: str
    rl_datum_m: float
    is_real_data: bool = True
    data_source: str = "aai_nocas"
    attempt: int = 1
