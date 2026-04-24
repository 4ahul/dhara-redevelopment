from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """Legacy session creation request."""
    society_id: UUID | None = None
    society_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)

class SessionResponse(BaseModel):
    """Legacy session response."""
    id: str
    society_name: str
    status: str
    created_at: datetime
    updated_at: datetime

class ChatMessage(BaseModel):
    """Legacy chat message."""
    role: str
    content: str
    timestamp: datetime | None = None

class UserProfileResponse(BaseModel):
    """Legacy user profile response."""
    id: str
    email: str
    name: str
    role: str
    organization: str | None = None

class UserProfileUpdate(BaseModel):
    """Legacy user profile update request."""
    name: str | None = None
    organization: str | None = None
    phone: str | None = None



