from fastapi import APIRouter

from .admin import router as admin_domain
from .infra import router as infra_domain
from .infra.websocket import router as ws_router
from .pmc import router as pmc_domain
from .public import router as public_domain

api_router = APIRouter()

# Global API grouping under /api
app_router = APIRouter(prefix="/api")

# Include all domains
app_router.include_router(public_domain)
app_router.include_router(infra_domain)
app_router.include_router(pmc_domain)
app_router.include_router(admin_domain)

# Add to main API router
api_router.include_router(app_router)

__all__ = ["api_router", "ws_router"]
