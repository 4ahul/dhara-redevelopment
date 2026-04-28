"""
Dhara AI — Auth Schemas
Request/Response models for authentication endpoints.
"""

from pydantic import BaseModel, Field


class AuthResponse(BaseModel):
    """Success response after login/signup."""

    status: str = "success"
    access_token: str
    token_type: str = "bearer"
    user: "AuthUserInfo"


class AuthUserInfo(BaseModel):
    """User info returned in auth responses."""

    id: str
    email: str
    name: str
    role: str
    organization: str | None = None
    avatar_url: str | None = None


class MeResponse(BaseModel):
    """Full profile of the currently authenticated user."""

    id: str
    clerk_id: str | None = None
    email: str
    name: str
    role: str
    organization: str | None = None
    avatar_url: str | None = None
    phone: str | None = None


class TokenRefreshRequest(BaseModel):
    """Token refresh."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request."""

    current_password: str = Field(min_length=6)
    new_password: str = Field(min_length=8, max_length=128)
