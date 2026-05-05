from fastapi import APIRouter

from .landing import router as landing_router

router = APIRouter()
router.include_router(landing_router)
