from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .feasibility import router as feasibility_router
from .landing import router as landing_router
from .profile import router as profile_router
from .search import router as search_router
from .societies import router as societies_router
from .team import router as team_router
from .websocket import router as ws_router_module

api_router = APIRouter()

# Group standard application routes under /api
app_router = APIRouter(prefix="/api")
app_router.include_router(admin_router)
app_router.include_router(auth_router)
app_router.include_router(feasibility_router)
app_router.include_router(landing_router)
app_router.include_router(profile_router)
app_router.include_router(search_router)
app_router.include_router(societies_router)
app_router.include_router(team_router)

# Add to main API router
api_router.include_router(app_router)

# WebSocket router
ws_router = ws_router_module

__all__ = ["api_router", "ws_router"]




