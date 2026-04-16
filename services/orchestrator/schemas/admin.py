"""
Dhara AI — Admin Schemas
Request/Response models for admin portal endpoints.
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# ─── PMC Users ───────────────────────────────────────────────────────────────

class PMCUserResponse(BaseModel):
    """PMC user detail for admin view."""
    id: UUID
    email: str
    name: str
    phone: Optional[str] = None
    organization: Optional[str] = None
    role: str
    is_active: bool
    societies_count: int = 0
    reports_count: int = 0
    last_login_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Enquiries ──────────────────────────────────────────────────────────────

class EnquiryResponse(BaseModel):
    """Full enquiry detail for admin view."""
    id: UUID
    name: str
    email: str
    phone: Optional[str] = None
    subject: Optional[str] = None
    message: str
    source: str
    status: str
    assigned_to: Optional[UUID] = None
    assigned_user_name: Optional[str] = None
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EnquiryUpdate(BaseModel):
    """Partial update for an enquiry (admin)."""
    status: Optional[str] = Field(default=None, pattern="^(new|in_progress|resolved|closed)$")
    assigned_to: Optional[UUID] = None
    admin_notes: Optional[str] = Field(default=None, max_length=5000)


# ─── Roles ───────────────────────────────────────────────────────────────────

class RoleResponse(BaseModel):
    """Role definition response."""
    id: UUID
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: Optional[dict] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    """Create a role (admin only)."""
    name: str = Field(min_length=2, max_length=100)
    display_name: str = Field(min_length=2, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    permissions: Optional[dict] = None
