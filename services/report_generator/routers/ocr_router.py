"""
OCR Router — wraps ocr_dhara_v2 extraction logic as a FastAPI endpoint.

POST /ocr/document     — upload a PDF file (multipart/form-data)
POST /ocr/extract      — send base64-encoded PDF bytes in JSON body

Both return the same structured dict:
  {
    "Society Age":                       "2006",
    "Number of Flats/Tenaments":         "22",
    "Number of Commercial Shops":        "4",
    "Existing Commercial area in sq ft": "1076.40",
    "Existing Residential area in sq ft":"21940.08",
    "Existing Built Up Area":            "23027.69",
    "PFA original OC":                   "14316.12"
  }
"""

from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ocr", tags=["OCR"])


# ── Lazy import of OCR logic ───────────────────────────────────────────────────
def _get_extractor():
    """Lazily import extract_from_pdf to avoid loading heavy deps at startup."""
    try:
        import sys

        # ocr_dhara_v2 lives at the repo root — two levels up from this file
        repo_root = Path(__file__).resolve().parents[3]
        ocr_dir = repo_root / "ocr_dhara_v2"
        if str(ocr_dir) not in sys.path:
            sys.path.insert(0, str(ocr_dir))
        from main import extract_from_pdf  # noqa: PLC0415

        return extract_from_pdf
    except ImportError as e:
        raise RuntimeError(f"ocr_dhara_v2 dependencies not installed: {e}") from e


# ── Request/Response schemas ───────────────────────────────────────────────────


class OcrExtractRequest(BaseModel):
    """Send PDF as base64-encoded bytes."""

    pdf_base64: str
    filename: str | None = "document.pdf"


class OcrResult(BaseModel):
    society_age: str | None = None
    num_flats: str | None = None
    num_commercial: str | None = None
    commercial_area_sqft: str | None = None
    residential_area_sqft: str | None = None
    existing_bua_sqft: str | None = None
    pfa_sqft: str | None = None
    raw: dict = {}


def _map_raw(raw: dict) -> OcrResult:
    return OcrResult(
        society_age=raw.get("Society Age") or None,
        num_flats=raw.get("Number of Flats/Tenaments") or None,
        num_commercial=raw.get("Number of Commercial Shops") or None,
        commercial_area_sqft=raw.get("Existing Commercial area in sq ft") or None,
        residential_area_sqft=raw.get("Existing Residential area in sq ft") or None,
        existing_bua_sqft=raw.get("Existing Built Up Area") or None,
        pfa_sqft=raw.get("PFA original OC") or None,
        raw=raw,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/document", response_model=OcrResult, summary="Extract fields from an uploaded PDF")
async def ocr_document(
    file: UploadFile = File(..., description="Building document PDF (OC / Plan / Completion Cert)"),
):
    """
    Upload a PDF building document and extract structured fields using Gemini Vision.

    The extraction runs Gemini on a 3×3 tiled grid of each page and votes on
    the most common value per field across all tiles.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(413, "PDF must be ≤ 50 MB")

    try:
        extract_from_pdf = _get_extractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        raw = extract_from_pdf(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
        return _map_raw(raw)

    except RuntimeError as e:
        raise HTTPException(503, f"OCR service not available: {e}") from e
    except Exception as e:
        logger.exception("OCR extraction failed")
        raise HTTPException(500, f"OCR extraction failed: {e}") from e


@router.post("/extract", response_model=OcrResult, summary="Extract fields from base64-encoded PDF")
async def ocr_extract(req: OcrExtractRequest):
    """
    Send a PDF as a base64 string and get back structured fields.
    Useful when the client already has the PDF bytes in memory.
    """
    try:
        pdf_bytes = base64.b64decode(req.pdf_base64)
    except Exception as e:
        raise HTTPException(400, "Invalid base64 encoding") from e

    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(413, "PDF must be ≤ 50 MB")

    try:
        extract_from_pdf = _get_extractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        raw = extract_from_pdf(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
        return _map_raw(raw)

    except RuntimeError as e:
        raise HTTPException(503, f"OCR service not available: {e}") from e
    except Exception as e:
        logger.exception("OCR extraction failed")
        raise HTTPException(500, f"OCR extraction failed: {e}") from e
