"""
Dhara AI — Landing Page Schemas
Request/Response models for landing page endpoints.
"""

from pydantic import BaseModel, EmailStr, Field


class GetStartedRequestSchema(BaseModel):
    """'Get Started' form submission from landing page."""

    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    society_name: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=1000)
    message: str | None = Field(default=None, max_length=2000)


class ContactRequestSchema(BaseModel):
    """'Talk to Us' form submission from landing page."""

    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    subject: str | None = Field(default=None, max_length=500)
    message: str = Field(min_length=10, max_length=5000)


class LandingPageSection(BaseModel):
    """A single content section on the landing page."""

    section: str
    title: str
    subtitle: str | None = None
    content: str | None = None
    media_url: str | None = None
    cta_text: str | None = None
    cta_url: str | None = None
    display_order: int = 0


class LandingPageResponse(BaseModel):
    """Full landing page content response."""

    sections: list[LandingPageSection] = []


class FormSubmissionResponse(BaseModel):
    """Generic response after submitting a landing page form."""

    status: str = "success"
    message: str
    reference_id: str
