import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ...core.dependencies import get_admin_service, require_admin
from ...schemas.admin import EnquiryResponse, EnquiryUpdate, RoleResponse
from ...schemas.common import PaginatedResponse
from ...services.admin_service import AdminService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin Portal"], dependencies=[Depends(require_admin)])


@router.get("/pmc-users", response_model=PaginatedResponse)
async def list_pmc_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None, max_length=200),
    is_active: bool = Query(None),
    service: AdminService = Depends(get_admin_service),
):
    """List all registered PMC users with status filters."""
    return await service.list_pmc_users(page, page_size, search, is_active)


@router.get("/search", response_model=PaginatedResponse)
async def admin_search(
    q: str = Query(min_length=1, max_length=500),
    entity_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: AdminService = Depends(get_admin_service),
):
    """Admin-level global search across all entities."""
    return await service.admin_search(q, entity_type, page, page_size)


@router.get("/enquiries", response_model=PaginatedResponse)
async def list_enquiries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    source: str = Query(None),
    service: AdminService = Depends(get_admin_service),
):
    """List landing page enquiries and leads."""
    return await service.list_enquiries(page, page_size, status, source)


@router.get("/enquiries/{enquiry_id}", response_model=EnquiryResponse)
async def get_enquiry(enquiry_id: UUID, service: AdminService = Depends(get_admin_service)):
    """Fetch full details of a specific enquiry."""
    return await service.get_enquiry(enquiry_id)


@router.patch("/enquiries/{enquiry_id}", response_model=EnquiryResponse)
async def patch_enquiry(
    enquiry_id: UUID, req: EnquiryUpdate, service: AdminService = Depends(get_admin_service)
):
    """Update status or notes of an enquiry."""
    return await service.patch_enquiry(enquiry_id, req.model_dump(exclude_unset=True))


@router.get("/roles", response_model=list[RoleResponse])
async def admin_roles(service: AdminService = Depends(get_admin_service)):
    """Manage global user roles."""
    roles = await service.get_roles()
    return [RoleResponse.model_validate(r) for r in roles]
