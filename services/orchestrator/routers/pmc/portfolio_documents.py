import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from ...core.dependencies import get_current_user, get_profile_service
from ...schemas.profile import (
    PortfolioDocumentListResponse,
    PortfolioDocumentResponse,
)
from ...services.profile_service import ProfileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio-documents", tags=["Portfolio Documents"])


@router.get("", response_model=PortfolioDocumentListResponse)
async def list_portfolio_documents(
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    """List all portfolio documents for the current user (returns array)."""
    docs = await service.list_portfolio_documents(user)
    return PortfolioDocumentListResponse(data=docs)


@router.post("", response_model=list[PortfolioDocumentResponse])
async def upload_portfolio_documents(
    files: list[UploadFile] = File(...),
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    """Upload multiple portfolio documents (PDF, images)."""
    return await service.upload_multiple_portfolios(user, files)


@router.delete("/{document_id}", status_code=204)
async def delete_portfolio_document(
    document_id: UUID,
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    """Delete a portfolio document by ID."""
    await service.delete_portfolio_document(user, document_id)
    return
