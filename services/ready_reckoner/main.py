from dhara_shared.dhara_common.banner import print_banner
from dhara_shared.dhara_common.tracing import setup_tracing
import logging
from fastapi import FastAPI
from services.ready_reckoner.core import settings
from services.ready_reckoner.routers.premium_router import router

from dhara_shared.dhara_common.logging import setup_logging
from dhara_shared.dhara_common.exceptions import setup_exception_handlers

print_banner(settings.APP_NAME)

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)
setup_tracing(app, settings.APP_NAME)

setup_exception_handlers(app)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ready_reckoner"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)







