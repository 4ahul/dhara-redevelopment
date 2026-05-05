"""
PMC Domain Router Hub.
Aggregates all PMC-facing modules under the /pmc prefix.
"""

from fastapi import APIRouter

from .profile import router as profile_router
from .reports import router as global_reports_router
from .search import router as search_router
from .societies import core_router, reports_router, tenders_router
from .team import router as team_router
from .verification import router as verification_router

router = APIRouter(prefix="/pmc")

# Include sub-routers
router.include_router(global_reports_router)

# Societies Domain (Split across files but sharing same prefix)
router.include_router(core_router, prefix="/societies")
router.include_router(reports_router, prefix="/societies")
router.include_router(tenders_router, prefix="/societies")

router.include_router(verification_router)
router.include_router(search_router)
router.include_router(team_router)
router.include_router(profile_router)
