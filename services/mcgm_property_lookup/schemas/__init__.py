"""
MCGM Property Lookup — Pydantic Schemas
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, field_validator


class Ward(StrEnum):
    """The 24 MCGM administrative wards, exactly as stored in the ArcGIS layer
    and shown in the WebApp Ward dropdown."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F_N = "F/N"
    F_S = "F/S"
    G_N = "G/N"
    G_S = "G/S"
    H_E = "H/E"
    H_W = "H/W"
    K_E = "K/E"
    K_W = "K/W"
    L = "L"
    M_E = "M/E"
    M_W = "M/W"
    N = "N"
    P_N = "P/N"
    P_S = "P/S"
    R_C = "R/C"
    R_N = "R/N"
    R_S = "R/S"
    S = "S"
    T = "T"


class PropertyLookupRequest(BaseModel):
    ward: Ward  # e.g. "K/W" — must be one of the 24 MCGM wards
    village: str  # e.g. "MANDVI" — normalised to uppercase
    cts_no: str  # e.g. "854" (CTS), "VI/18" (FP), "123/1/A"
    tps_name: str | None = None  # TPS scheme name (e.g. "VILE PARLE") - for FP search
    use_fp: bool = False  # Set True if searching by FP number (e.g. "VI/18")
    include_nearby: bool = True  # also fetch adjacent plot CTS numbers

    @field_validator("village")
    @classmethod
    def _upper_village(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("cts_no")
    @classmethod
    def _clean_cts(cls, v: str) -> str:
        return v.strip()

    @field_validator("use_fp", mode="before")
    @classmethod
    def _detect_fp(cls, v: bool, info) -> bool:
        """Auto-detect FP format from cts_no field."""
        # If use_fp already explicitly set, use that
        if v is not None:
            return v
        return False


class PropertyLookupStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class NearbyProperty(BaseModel):
    cts_no: str
    tps_name: str | None = None
    ward: str | None = None


class PropertyLookupResponse(BaseModel):
    id: str | None = None
    status: PropertyLookupStatus
    ward: str | None = None
    village: str | None = None
    cts_no: str | None = None
    tps_name: str | None = None  # TPS scheme name
    fp_no: str | None = None  # Final Plot No (same as CTS in many cases)
    geometry_wgs84: list | None = None  # polygon coordinates [[lng, lat], ...]
    centroid_lat: float | None = None
    centroid_lng: float | None = None
    area_sqm: float | None = None
    nearby_properties: list[NearbyProperty] | None = None
    setback_area_m2: float | None = None
    max_road_width_m: float | None = None
    abutting_length_m: float | None = None
    reservation_area_m2: float | None = None
    nalla_present: bool | None = None
    industrial_present: bool | None = None
    zone_code: str | None = None
    roads_touching: int | None = None
    carriageway_entrances: int | None = None
    download_url: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
