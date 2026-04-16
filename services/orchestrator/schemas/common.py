"""
Dhara AI — Common Schemas
Shared pagination, search, and response wrappers.
"""

from typing import Optional, Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort direction")


class PaginatedResponse(BaseModel):
    """Wrapper for paginated list responses."""
    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


class SearchParams(BaseModel):
    """Query parameters for search endpoints."""
    q: str = Field(min_length=1, max_length=500, description="Search query")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    entity_type: Optional[str] = Field(default=None, description="Filter by entity type: society, report, user, enquiry")


class MessageResponse(BaseModel):
    """Generic message response."""
    status: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    status: str = "error"
    detail: str
    code: Optional[str] = None
