from pydantic import BaseModel


class HeightRequest(BaseModel):
    lat: float
    lng: float
    site_elevation: float | None = None


class HeightResponse(BaseModel):
    lat: float
    lng: float
    site_elevation: float
    elevation_source: str | None = None
    max_height_m: float | None = None
    max_floors: int | None = None
    restriction_reason: str
    nocas_reference: str | None = None
    aai_zone: str | None = None
    rl_datum_m: float | None = None
    is_real_data: bool = True
    data_source: str = "aai_nocas"
    error: str | None = None
