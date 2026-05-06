from fastapi import APIRouter

from .address import router as address_router
from .landing import router as landing_router

router = APIRouter()
router.include_router(address_router)
router.include_router(landing_router)
