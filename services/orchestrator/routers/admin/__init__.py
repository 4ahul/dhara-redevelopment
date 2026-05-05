from fastapi import APIRouter

from .admin import router as admin_portal_router

router = APIRouter()
router.include_router(admin_portal_router)
