"""
MCGM Property Lookup — Pydantic Schemas
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class PropertyLookupRequest(BaseModel):
    ward: str                   # e.g. "B"
    village: str                # e.g. "MANDVI"
    cts_no: str                 # e.g. "100"
    include_nearby: bool = True  # also fetch adjacent plot CTS numbers


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
