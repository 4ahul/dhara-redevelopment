"""
Dhara AI — Profile Schemas
Request/Response models for user profile and portfolio endpoints.
"""

from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class ProfileResponse(BaseModel):
    """Full user profile response."""
    id: UUID
    email: str
    name: str
    phone: Optional[str] = None
    organization: Optional[str] = None
    role: str
    portfolio_url: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    """Partial update for user profile."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20, pattern=r"^\+?[\d\s\-]{7,20}$")
    organization: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


class PortfolioUploadResponse(BaseModel):
    """Response after uploading a portfolio file."""
    status: str = "success"
    portfolio_url: str
    public_id: str
    format: str
    size_bytes: int
