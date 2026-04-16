from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class SessionCreate(BaseModel):
    """Legacy session creation request."""
    society_id: Optional[UUID] = None
    society_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

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
    timestamp: Optional[datetime] = None

class UserProfileResponse(BaseModel):
    """Legacy user profile response."""
    id: str
    email: str
    name: str
    role: str
    organization: Optional[str] = None

class UserProfileUpdate(BaseModel):
    """Legacy user profile update request."""
    name: Optional[str] = None
    organization: Optional[str] = None
    phone: Optional[str] = None
