"""Admin Portal Routes — PMC users, enquiries, roles, stats"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..core.dependencies import get_admin_service, require_admin
from ..schemas.admin import EnquiryResponse, EnquiryUpdate, RoleResponse
from ..schemas.common import PaginatedResponse
from ..services.admin_service import AdminService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin Portal"])


@router.get("/pmc-users", response_model=PaginatedResponse, dependencies=[Depends(require_admin)])
async def list_pmc_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None, max_length=200),
    is_active: bool = Query(None),
    service: AdminService = Depends(get_admin_service),
):
    return await service.list_pmc_users(page, page_size, search, is_active)


@router.get("/search", response_model=PaginatedResponse, dependencies=[Depends(require_admin)])
async def admin_search(
    q: str = Query(min_length=1, max_length=500),
    entity_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: AdminService = Depends(get_admin_service),
):
    return await service.admin_search(q, entity_type, page, page_size)


@router.get("/enquiries", response_model=PaginatedResponse, dependencies=[Depends(require_admin)])
async def list_enquiries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    source: str = Query(None),
    service: AdminService = Depends(get_admin_service),
):
    return await service.list_enquiries(page, page_size, status, source)


@router.get(
    "/enquiries/{enquiry_id}", response_model=EnquiryResponse, dependencies=[Depends(require_admin)]
)
async def get_enquiry(enquiry_id: UUID, service: AdminService = Depends(get_admin_service)):
    return await service.get_enquiry(enquiry_id)


@router.patch(
    "/enquiries/{enquiry_id}", response_model=EnquiryResponse, dependencies=[Depends(require_admin)]
)
async def patch_enquiry(
    enquiry_id: UUID, req: EnquiryUpdate, service: AdminService = Depends(get_admin_service)
):
    return await service.patch_enquiry(enquiry_id, req.model_dump(exclude_unset=True))


@router.get("/roles", response_model=list[RoleResponse], dependencies=[Depends(require_admin)])
async def admin_roles(service: AdminService = Depends(get_admin_service)):
    roles = await service.get_roles()
    return [RoleResponse.model_validate(r) for r in roles]
