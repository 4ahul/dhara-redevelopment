from dhara_shared.dhara_common.banner import print_banner
import sys, os
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path: sys.path.insert(0, _dir)
_root = os.path.dirname(os.path.dirname(_dir))
if _root not in sys.path: sys.path.append(_root)
import sys
import os
from pathlib import Path

# Fix pathing for standalone execution and internal service imports
SERVICE_ROOT = str(Path(os.path.abspath(__file__)).resolve().parent)
MONOREPO_ROOT = str(Path(SERVICE_ROOT).resolve().parent.parent)

for p in [SERVICE_ROOT, MONOREPO_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)
"""
Height Service - NOCAS Building Height Verification
Main entry point.
"""

import sys
import os
import logging
from pathlib import Path

service_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(service_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if service_dir not in sys.path:
    sys.path.insert(0, service_dir); sys.path.insert(0, os.path.join(service_dir, 'services'))

from fastapi import FastAPI
from services.aviation_height.core import settings
from services.aviation_height.routers.height_router import router

from services.aviation_height.core.banner import print_banner as _print_banner


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

print_banner(settings.APP_NAME)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "aviation_height"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)






