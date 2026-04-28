import os
import sys

# Add the repo root so that "services.xxx" imports work
_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo not in sys.path:
    sys.path.insert(0, _repo)
