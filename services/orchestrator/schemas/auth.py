"""
Dhara AI — Auth Schemas
Request/Response models for authentication endpoints.
"""


from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """PMC / Admin login request."""
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class SignupRequest(BaseModel):
    """PMC signup request — creates user account."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^\+?[\d\s\-]{7,20}$")
    organization: str | None = Field(default=None, max_length=255)


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



