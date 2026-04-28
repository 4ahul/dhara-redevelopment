"""
Dhara AI — Team Schemas
Request/Response models for team management and invitations.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TeamMemberResponse(BaseModel):
    """Team member detail response."""

    id: UUID
    user_id: UUID | None = None
    organization: str
    role: str
    email: str
    name: str | None = None
    status: str
    invited_by: UUID
    joined_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamMemberUpdate(BaseModel):
    """Update a team member's role or details."""

    role: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=255)


class InviteRequest(BaseModel):
    """Invite a new team member via email."""

    email: EmailStr
    name: str | None = Field(default=None, max_length=255)
    role: str = Field(default="member", max_length=100)


class InviteResponse(BaseModel):
    """Response after sending an invitation."""

    status: str = "success"
    message: str
    invite_id: UUID
    email: str
