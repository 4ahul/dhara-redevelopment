"""
Dhara AI -- Profile Schemas
Request/Response models for user profile and portfolio endpoints.
FE-aligned: camelCase serialization for PMC company profile fields.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    """Full user profile response -- serialized as camelCase for FE."""

    id: UUID
    email: str
    name: str
    phone: str | None = None
    organization: str | None = Field(default=None, serialization_alias="companyName")
    role: str
    # PMC company profile fields
    registration_number: str | None = Field(default=None, serialization_alias="registrationNumber")
    website: str | None = None
    address: str | None = None
    experience: str | None = None
    projects_completed: str | None = Field(default=None, serialization_alias="projectsCompleted")
    specialization: str | None = None
    portfolio_description: str | None = Field(default=None, serialization_alias="portfolio")
    country: str | None = None
    portfolio_url: str | None = Field(default=None, serialization_alias="portfolioUrl")
    avatar_url: str | None = Field(default=None, serialization_alias="avatarUrl")
    is_active: bool = Field(serialization_alias="isActive")
    last_login_at: datetime | None = Field(default=None, serialization_alias="lastLoginAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ProfileUpdate(BaseModel):
    """Partial update for user profile -- accepts FE camelCase."""

    name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^\+?[\d\s\-]{7,20}$")
    organization: str | None = Field(default=None, max_length=255, alias="companyName")
    registration_number: str | None = Field(
        default=None, max_length=100, alias="registrationNumber"
    )
    website: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None)
    experience: str | None = Field(default=None, max_length=100)
    projects_completed: str | None = Field(default=None, max_length=100, alias="projectsCompleted")
    specialization: str | None = Field(default=None, max_length=255)
    portfolio_description: str | None = Field(default=None, alias="portfolio")
    country: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500, alias="avatarUrl")

    model_config = {"populate_by_name": True}


class PortfolioUploadResponse(BaseModel):
    """Response after uploading a portfolio file."""

    status: str = "success"
    portfolio_url: str = Field(serialization_alias="portfolioUrl")
    public_id: str = Field(serialization_alias="publicId")
    format: str
    size_bytes: int = Field(serialization_alias="sizeBytes")

    model_config = {"populate_by_name": True}
