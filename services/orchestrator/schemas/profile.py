"""
Dhara AI — Profile Schemas
Request/Response models for user profile and portfolio endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    """Full user profile response."""
    id: UUID
    email: str
    name: str
    phone: str | None = None
    organization: str | None = None
    role: str
    portfolio_url: str | None = None
    avatar_url: str | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    """Partial update for user profile."""
    name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^\+?[\d\s\-]{7,20}$")
    organization: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=500)


class PortfolioUploadResponse(BaseModel):
    """Response after uploading a portfolio file."""
    status: str = "success"
    portfolio_url: str
    public_id: str
    format: str
    size_bytes: int



