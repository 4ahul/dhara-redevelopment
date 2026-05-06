from typing import Any

from pydantic import BaseModel, Field


class InternalServiceResponse(BaseModel):
    """Standardized wrapper for responses between internal microservices."""

    status: str = Field(..., description="'success' or 'error'")
    data: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class Dossier(BaseModel):
    """Strictly typed schema for the dossier payload passed to the report generator."""

    society_name: str
    scheme: str
    redevelopment_type: str
    ward: str | None = None
    plot_area_sqm: float
    road_width_m: float
    num_flats: int
    num_commercial: int
    society_age: int | None = None
    existing_bua_sqft: float
    existing_residential_carpet_sqft: float
    existing_commercial_carpet_sqft: float

    # Nested microservice data blocks
    mcgm_property: dict[str, Any] = Field(default_factory=dict)
    dp_report: dict[str, Any] = Field(default_factory=dict)
    site_analysis: dict[str, Any] = Field(default_factory=dict)
    height: dict[str, Any] = Field(default_factory=dict)
    ready_reckoner: dict[str, Any] = Field(default_factory=dict)
    financial: dict[str, Any] = Field(default_factory=dict)
    manual_inputs: dict[str, Any] = Field(default_factory=dict)
    premium: dict[str, Any] = Field(default_factory=dict)
    zone_regulations: dict[str, Any] = Field(default_factory=dict)
    fsi: dict[str, Any] = Field(default_factory=dict)
    bua: dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"  # Allow extra fields for backward compatibility while adopting
