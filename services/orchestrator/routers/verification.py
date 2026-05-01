"""PMC Verification Routes — LS and Architect

Endpoints are PMC-only. They delegate registration number extraction to the
OCR service, then perform verification locally via upstream portals.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..core.config import settings
from ..core.dependencies import require_pmc
from ..services.pmc_verification import verify_architect, verify_licensed_surveyor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/verify", tags=["PMC Verification"], dependencies=[Depends(require_pmc)])


ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
MAX_BYTES = 15 * 1024 * 1024  # 15 MB


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse(
        {"valid": False, "reason": "invalid_input", "message": message}, status_code=400
    )


async def _read_and_validate(file: UploadFile | None) -> tuple[bytes, str]:
    if file is None:
        raise HTTPException(400, "A certificate file is required.")
    content = await file.read()
    if not content:
        raise HTTPException(400, "A certificate file is required.")
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(400, "Unsupported file type. Upload a PDF, JPG, PNG or WebP.")
    if len(content) > MAX_BYTES:
        raise HTTPException(400, "File too large. Max 15 MB.")
    return content, file.content_type


@router.post("/license-surveyor")
async def verify_license_surveyor(file: UploadFile = File(...)):
    content, mime = await _read_and_validate(file)

    # 1) Ask OCR service for LS registration extraction
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.OCR_URL}/ls/extract-registration",
                files={"file": ((file.filename or "certificate"), content, mime)},
                data={"strategy": "auto", "lang": "eng"},
            )
            resp.raise_for_status()
            extraction = resp.json()
    except httpx.HTTPStatusError as e:
        logger.exception("OCR service returned %s", e.response.status_code)
        return JSONResponse(
            {
                "valid": False,
                "reason": "upstream_error",
                "message": f"OCR service error: {e.response.status_code}",
            },
            status_code=502,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("OCR extraction failed")
        return JSONResponse(
            {
                "valid": False,
                "reason": "upstream_error",
                "message": str(e) or "OCR service call failed",
            },
            status_code=502,
        )

    if not extraction.get("ok"):
        # Surface extraction errors directly to the caller
        return {"valid": False, **extraction}

    reg_no = extraction["registrationNumber"]

    # 2) Verify upstream
    try:
        result = await verify_licensed_surveyor(reg_no)
    except Exception as e:  # noqa: BLE001
        logger.exception("verify license-surveyor failed")
        return JSONResponse(
            {
                "valid": False,
                "reason": "upstream_error",
                "message": str(e) or "Failed to verify Licensed Surveyor.",
            },
            status_code=502,
        )

    return {
        **result,
        "extractedRegistrationNumber": reg_no,
        "usedOcr": extraction.get("usedOcr", False),
    }


@router.post("/architect")
async def verify_architect_endpoint(file: UploadFile = File(...)):
    content, mime = await _read_and_validate(file)

    # 1) Ask OCR service for Architect registration extraction
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.OCR_URL}/architect/extract-registration",
                files={"file": ((file.filename or "certificate"), content, mime)},
                data={"strategy": "auto", "lang": "eng"},
            )
            resp.raise_for_status()
            extraction = resp.json()
    except httpx.HTTPStatusError as e:
        logger.exception("OCR service returned %s", e.response.status_code)
        return JSONResponse(
            {
                "valid": False,
                "reason": "upstream_error",
                "message": f"OCR service error: {e.response.status_code}",
            },
            status_code=502,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("OCR extraction failed")
        return JSONResponse(
            {
                "valid": False,
                "reason": "upstream_error",
                "message": str(e) or "OCR service call failed",
            },
            status_code=502,
        )

    if not extraction.get("ok"):
        return {"valid": False, **extraction}

    reg_no = extraction["registrationNumber"]

    # 2) Verify upstream
    try:
        result = await verify_architect(reg_no)
    except Exception as e:  # noqa: BLE001
        logger.exception("verify architect failed")
        return JSONResponse(
            {
                "valid": False,
                "reason": "upstream_error",
                "message": str(e) or "Failed to verify Architect.",
            },
            status_code=502,
        )

    return {
        **result,
        "extractedRegistrationNumber": reg_no,
        "usedOcr": extraction.get("usedOcr", False),
    }
