"""
MCGM Property Lookup — Pydantic Schemas
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class Ward(str, Enum):
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
    ward: Ward                   # e.g. "K/W" — must be one of the 24 MCGM wards
    village: str                 # e.g. "MANDVI" — normalised to uppercase
    cts_no: str                  # e.g. "854", "1234/56", "123/1/A", "123-124", "123+124"
    include_nearby: bool = True  # also fetch adjacent plot CTS numbers

    @field_validator("village")
    @classmethod
    def _upper_village(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("cts_no")
    @classmethod
    def _clean_cts(cls, v: str) -> str:
        return v.strip()


class PropertyLookupStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class NearbyProperty(BaseModel):
    cts_no: str
    tps_name: Optional[str] = None
    ward: Optional[str] = None


class PropertyLookupResponse(BaseModel):
    id: Optional[str] = None
    status: PropertyLookupStatus
    ward: Optional[str] = None
    village: Optional[str] = None
    cts_no: Optional[str] = None
    tps_name: Optional[str] = None       # TPS scheme name
    fp_no: Optional[str] = None          # Final Plot No (same as CTS in many cases)
    geometry_wgs84: Optional[list] = None  # polygon coordinates [[lng, lat], ...]
    centroid_lat: Optional[float] = None
    centroid_lng: Optional[float] = None
    area_sqm: Optional[float] = None
    nearby_properties: Optional[list[NearbyProperty]] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
