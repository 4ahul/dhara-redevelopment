"""
Dhara AI — Landing Page Schemas
Request/Response models for landing page endpoints.
"""

from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class GetStartedRequestSchema(BaseModel):
    """'Get Started' form submission from landing page."""
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=20)
    society_name: Optional[str] = Field(default=None, max_length=500)
    address: Optional[str] = Field(default=None, max_length=1000)
    message: Optional[str] = Field(default=None, max_length=2000)


class ContactRequestSchema(BaseModel):
    """'Talk to Us' form submission from landing page."""
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=20)
    subject: Optional[str] = Field(default=None, max_length=500)
    message: str = Field(min_length=10, max_length=5000)


class LandingPageSection(BaseModel):
    """A single content section on the landing page."""
    section: str
    title: str
    subtitle: Optional[str] = None
    content: Optional[str] = None
    media_url: Optional[str] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    display_order: int = 0


class LandingPageResponse(BaseModel):
    """Full landing page content response."""
    sections: List[LandingPageSection] = []


class FormSubmissionResponse(BaseModel):
    """Generic response after submitting a landing page form."""
    status: str = "success"
    message: str
    reference_id: str
