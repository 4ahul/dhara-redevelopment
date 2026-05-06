"""
Dhara AI -- Team Schemas
Request/Response models for team management and invitations.
FE-aligned: camelCase serialization, roles as array, status mapping.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Valid PMC roles the FE expects
PMC_ROLES = {"pmc_admin", "pmc_report_analyst", "pmc_tender_manager"}

# Map BE InviteStatus values to FE display values
_STATUS_MAP = {
    "accepted": "active",
    "pending": "pending",
    "declined": "declined",
    "expired": "expired",
}


class TeamMemberResponse(BaseModel):
    """Team member detail -- serialized as camelCase for FE."""

    id: UUID
    user_id: UUID | None = Field(default=None, serialization_alias="userId")
    organization: str
    roles: list[str] = Field(default_factory=list, description="FE expects array of role strings")
    email: str
    name: str | None = None
    status: str
    enabled: bool = Field(default=True)
    invited_by: UUID = Field(serialization_alias="invitedBy")
    joined_at: datetime | None = Field(default=None, serialization_alias="joinedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _map_fields(cls, data: Any) -> Any:
        """Convert ORM object: single role->roles array, is_enabled->enabled, status mapping."""
        if hasattr(data, "__dict__"):
            # ORM object
            d = {}
            for k in (
                "id",
                "user_id",
                "organization",
                "email",
                "name",
                "invited_by",
                "joined_at",
                "created_at",
                "updated_at",
            ):
                d[k] = getattr(data, k, None)
            # role (single string) -> roles (array)
            role_val = getattr(data, "role", "member")
            d["roles"] = [role_val] if role_val else []
            # is_enabled -> enabled
            d["enabled"] = getattr(data, "is_enabled", True)
            # status mapping: accepted -> active
            raw_status = str(getattr(data, "status", "pending"))
            # Handle enum objects
            if hasattr(raw_status, "value"):
                raw_status = raw_status.value
            d["status"] = _STATUS_MAP.get(raw_status, raw_status)
            return d
        return data


class TeamMemberUpdate(BaseModel):
    """Update team member -- accepts FE camelCase."""

    roles: list[str] | None = Field(default=None, description="Array of roles to set")
    name: str | None = Field(default=None, max_length=255)
    enabled: bool | None = Field(default=None, alias="enabled")

    model_config = {"populate_by_name": True}


class InviteRequest(BaseModel):
    """Invite a new team member via email."""

    email: EmailStr
    name: str | None = Field(default=None, max_length=255)
    role: str = Field(default="pmc_admin", max_length=100)

    model_config = {"populate_by_name": True}

    @field_validator("role")
    @classmethod
    def _validate_pmc_role(cls, v: str) -> str:
        if v not in PMC_ROLES:
            raise ValueError(f"role must be one of: {', '.join(sorted(PMC_ROLES))}")
        return v


class InviteResponse(BaseModel):
    """Response after sending an invitation."""

    status: str = "success"
    message: str
    invite_id: UUID = Field(serialization_alias="inviteId")
    email: str

    model_config = {"populate_by_name": True}
