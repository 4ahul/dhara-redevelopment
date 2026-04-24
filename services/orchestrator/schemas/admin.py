"""
Dhara AI — Admin Schemas
Request/Response models for admin portal endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ─── PMC Users ───────────────────────────────────────────────────────────────

class PMCUserResponse(BaseModel):
    """PMC user detail for admin view."""
    id: UUID
    email: str
    name: str
    phone: str | None = None
    organization: str | None = None
    role: str
    is_active: bool
    societies_count: int = 0
    reports_count: int = 0
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Enquiries ──────────────────────────────────────────────────────────────

class EnquiryResponse(BaseModel):
    """Full enquiry detail for admin view."""
    id: UUID
    name: str
    email: str
    phone: str | None = None
    subject: str | None = None
    message: str
    source: str
    status: str
    assigned_to: UUID | None = None
    assigned_user_name: str | None = None
    admin_notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EnquiryUpdate(BaseModel):
    """Partial update for an enquiry (admin)."""
    status: str | None = Field(default=None, pattern="^(new|in_progress|resolved|closed)$")
    assigned_to: UUID | None = None
    admin_notes: str | None = Field(default=None, max_length=5000)


# ─── Roles ───────────────────────────────────────────────────────────────────

class RoleResponse(BaseModel):
    """Role definition response."""
    id: UUID
    name: str
    display_name: str
    description: str | None = None
    permissions: dict | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    """Create a role (admin only)."""
    name: str = Field(min_length=2, max_length=100)
    display_name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    permissions: dict | None = None


