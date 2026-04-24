from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field

class InternalServiceResponse(BaseModel):
    """Standardized wrapper for responses between internal microservices."""
    status: str = Field(..., description="'success' or 'error'")
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class Dossier(BaseModel):
    """Strictly typed schema for the dossier payload passed to the report generator."""
    society_name: str
    scheme: str
    redevelopment_type: str
    ward: Optional[str] = None
    plot_area_sqm: float
    road_width_m: float
    num_flats: int
    num_commercial: int
    society_age: Optional[int] = None
    existing_bua_sqft: float
    existing_residential_carpet_sqft: float
    existing_commercial_carpet_sqft: float
    
    # Nested microservice data blocks
    mcgm_property: Dict[str, Any] = Field(default_factory=dict)
    dp_report: Dict[str, Any] = Field(default_factory=dict)
    site_analysis: Dict[str, Any] = Field(default_factory=dict)
    height: Dict[str, Any] = Field(default_factory=dict)
    ready_reckoner: Dict[str, Any] = Field(default_factory=dict)
    financial: Dict[str, Any] = Field(default_factory=dict)
    manual_inputs: Dict[str, Any] = Field(default_factory=dict)
    premium: Dict[str, Any] = Field(default_factory=dict)
    zone_regulations: Dict[str, Any] = Field(default_factory=dict)
    fsi: Dict[str, Any] = Field(default_factory=dict)
    bua: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        extra = "allow"  # Allow extra fields for backward compatibility while adopting
