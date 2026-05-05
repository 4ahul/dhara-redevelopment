"""
Society Domain Router Hub.
Groups core, reports, and tenders.
Prefix: /api/pmc/societies
"""

from .core import router as core_router
from .reports import router as reports_router
from .tenders import router as tenders_router

__all__ = ["core_router", "reports_router", "tenders_router"]
