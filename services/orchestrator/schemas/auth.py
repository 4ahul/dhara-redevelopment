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


class UserMetadata(BaseModel):
    """Nested user_metadata object expected by FE."""

    full_name: str | None = Field(default=None, serialization_alias="full_name")
    user_type: str | None = Field(default=None, serialization_alias="user_type")
    company_name: str | None = Field(default=None, serialization_alias="company_name")
    country: str | None = None


class MeResponse(BaseModel):
    """Full profile of the currently authenticated user.

    Includes both flat fields (for backward compat) and nested user_metadata (for FE).
    """

    id: str
    clerk_id: str | None = None
    email: str
    name: str
    role: str
    organization: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    user_metadata: UserMetadata | None = None


class LogoutResponse(BaseModel):
    """Logout confirmation."""

    status: str = "success"
    message: str = "Logged out successfully"


class TokenRefreshRequest(BaseModel):
    """Token refresh."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request."""

    current_password: str = Field(min_length=6)
    new_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Email/password login request."""

    email: str
    password: str


class SignupRequest(BaseModel):
    """User signup request."""

    email: str
    password: str
    name: str
    organization: str | None = None
    role: str | None = "pmc"
