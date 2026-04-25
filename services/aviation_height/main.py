from dhara_shared.dhara_common.banner import print_banner
from dhara_shared.dhara_common.tracing import setup_tracing
import logging
from fastapi import FastAPI
from services.aviation_height.core import settings
from services.aviation_height.routers.height_router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

print_banner(settings.APP_NAME)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)
setup_tracing(app, settings.APP_NAME)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "aviation_height"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)






