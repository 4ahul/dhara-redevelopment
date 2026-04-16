"""
Dhara AI — Cloudinary File Service
Production-ready file upload, download, and deletion via Cloudinary SDK.
"""

import logging
import cloudinary
import cloudinary.uploader
import cloudinary.api
from io import BytesIO
from typing import Optional
from fastapi import UploadFile, HTTPException
from core.config import settings

logger = logging.getLogger(__name__)

_initialized = False

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOCUMENT_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
ALLOWED_ALL = ALLOWED_IMAGE_TYPES | ALLOWED_DOCUMENT_TYPES
MAX_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _ensure_init():
    global _initialized
    if not _initialized:
        if not all([settings.CLOUDINARY_CLOUD_NAME, settings.CLOUDINARY_API_KEY, settings.CLOUDINARY_API_SECRET]):
            raise RuntimeError("Cloudinary not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET.")
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
        _initialized = True
        logger.info("Cloudinary initialized for cloud: %s", settings.CLOUDINARY_CLOUD_NAME)


async def upload_file(
    file: UploadFile,
    folder: str = "dhara",
    resource_type: str = "auto",
    allowed_types: Optional[set] = None,
    public_id: Optional[str] = None,
) -> dict:
    _ensure_init()
    if allowed_types is None:
        allowed_types = ALLOWED_ALL

    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"File type '{file.content_type}' not allowed.")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {settings.MAX_UPLOAD_SIZE_MB} MB")

    opts = {"folder": folder, "resource_type": resource_type, "overwrite": True, "use_filename": True, "unique_filename": True}
    if public_id:
        opts["public_id"] = public_id

    try:
        result = cloudinary.uploader.upload(BytesIO(content), **opts)
        logger.info("Uploaded: %s (%s, %d bytes)", result["public_id"], result.get("format", "?"), result.get("bytes", 0))
        return {
            "url": result["url"], "secure_url": result["secure_url"],
            "public_id": result["public_id"], "format": result.get("format", ""),
            "bytes": result.get("bytes", 0), "resource_type": result.get("resource_type", ""),
            "width": result.get("width"), "height": result.get("height"),
        }
    except cloudinary.exceptions.Error as e:
        logger.error("Cloudinary upload failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Upload failed: {e}")
    except Exception as e:
        logger.error("Unexpected upload error: %s", e)
        raise HTTPException(status_code=500, detail="Upload failed unexpectedly")


async def upload_portfolio(file: UploadFile) -> dict:
    return await upload_file(file, folder="dhara/portfolios", allowed_types=ALLOWED_IMAGE_TYPES | {"application/pdf"})


async def upload_avatar(file: UploadFile) -> dict:
    return await upload_file(file, folder="dhara/avatars", resource_type="image", allowed_types=ALLOWED_IMAGE_TYPES)


async def upload_report(file: UploadFile) -> dict:
    return await upload_file(file, folder="dhara/reports", resource_type="raw", allowed_types=ALLOWED_DOCUMENT_TYPES)


def delete_file(public_id: str, resource_type: str = "image") -> bool:
    _ensure_init()
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return result.get("result") == "ok"
    except Exception as e:
        logger.error("Failed to delete %s: %s", public_id, e)
        return False
