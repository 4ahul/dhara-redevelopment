from dhara_shared.dhara_common.banner import print_banner
import logging
from fastapi import FastAPI
from services.report_generator.core.config import settings
from services.report_generator.routers.report_router import router
from services.report_generator.routers.ocr_router import router as ocr_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

print_banner(settings.APP_NAME)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "report_generator"}

app.include_router(router)
app.include_router(ocr_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)






