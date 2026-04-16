"""
Site Analysis Service
Main entry point for FastAPI application.
"""

import sys
import os
from pathlib import Path

# Add the service directory to sys.path to resolve internal imports (core, routers, etc.)
service_dir = os.path.dirname(os.path.abspath(__file__))
if service_dir not in sys.path:
    sys.path.append(service_dir)

from fastapi import FastAPI
from core import settings
from routers.site_router import router

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "site_analysis"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
