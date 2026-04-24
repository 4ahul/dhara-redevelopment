import sys, os
_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _dir not in sys.path: sys.path.insert(0, _dir)
from .premium_router import router

__all__ = ["router"]


