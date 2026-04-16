import asyncio
import base64
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)

from schemas import PRCardRequest, PRCardResponse, PRCardStatus

try:
    from services.browser import (
        create_browser_service,
        MahabhumiScraper as MahabhumiScraperSelenium,
    )
except ImportError as e:
    logger.error(
        "Real scraper unavailable — Playwright/browser dependencies missing: %s. "
        "Install with: pip install playwright && playwright install chromium", e
    )
    raise ImportError(
        f"PR Card Scraper requires Playwright browser dependencies: {e}"
    ) from e

from services.storage import AsyncStorageService as StorageService
from core import settings

router = APIRouter()


def get_storage() -> StorageService:
    return StorageService(settings.DATABASE_URL)


def _form_state_from_request(req: PRCardRequest) -> dict:
    """Extract the kwargs that scrape_pr_card accepts from a PRCardRequest."""
    return {
        "district": req.district,
        "taluka": req.taluka,
        "village": req.village,
        "survey_no": req.survey_no,
        "survey_no_part1": req.survey_no_part1,
        "mobile": req.mobile,
        "property_uid": req.property_uid,
        "property_uid_known": req.property_uid_known,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core scrape helper (reused by both async and sync endpoints)
# ─────────────────────────────────────────────────────────────────────────────

async def _do_scrape(pr_id: Optional[str], form_state: dict, storage: Optional[StorageService]) -> dict:
    """
    Run the full scrape flow. Persists result to DB if pr_id and storage are given.
    Returns the raw scraper result dict.

    CAPTCHA is handled entirely internally by the scraper (auto-solver, 3 retries).
    If all retries fail the scraper returns status="captcha_required" which is
    persisted as "failed" — no manual input, no user involvement.
    """
    browser = None
    try:
        browser = create_browser_service(headless=settings.BROWSER_HEADLESS)
        await browser.start()
        scraper = MahabhumiScraperSelenium(browser)

        # No on_captcha callback — CAPTCHA is the scraper's internal concern.
        result = await scraper.scrape_pr_card(**form_state)

        if pr_id and storage:
            await _persist_result(storage, pr_id, result)

        return result

    except Exception as e:
        logger.error(f"Scraper error (pr_id={pr_id}): {e}", exc_info=True)
        if pr_id and storage:
            await storage.update_pr_card(pr_id=pr_id, status="failed", error_message=str(e))
        return {"status": "failed", "error": str(e)}
    finally:
        if browser:
            await browser.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Async endpoint — returns immediately, processes in background
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/scrape", response_model=PRCardResponse)
async def scrape_pr_card(req: PRCardRequest, background_tasks: BackgroundTasks):
    """
    Submit a PR Card extraction request (processed asynchronously).
    Poll GET /status/{id} for result.
    """
    storage = get_storage()
    form_state = _form_state_from_request(req)

    pr_id = await storage.create_pr_card(
        district=req.district,
        taluka=req.taluka,
        village=req.village,
        survey_no=req.survey_no,
        survey_no_part1=req.survey_no_part1,
        mobile=req.mobile,
        property_uid=req.property_uid,
        property_uid_known=req.property_uid_known,
        record_of_right=req.record_of_right.value,
        language=req.language,
    )

    background_tasks.add_task(_do_scrape, pr_id, form_state, storage)

    pr_card = await storage.get_pr_card(pr_id)
    created_at = pr_card["created_at"] if pr_card else datetime.utcnow()

    return PRCardResponse(
        id=pr_id,
        status=PRCardStatus.PROCESSING,
        district=req.district,
        taluka=req.taluka,
        village=req.village,
        survey_no=req.survey_no,
        created_at=created_at,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Synchronous endpoint — for orchestrator / direct callers
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/scrape/sync", response_model=PRCardResponse)
async def scrape_pr_card_sync(req: PRCardRequest, request: Request):
    """
    Synchronous PR Card extraction — waits for completion before responding.
    Designed for the orchestrator agent which needs the result in a single call.

    Returns image as base64 in `image_b64`.
    Creates a DB record so the image can also be downloaded via GET /download/{id}.
    """
    storage = get_storage()
    form_state = _form_state_from_request(req)

    # Create DB record (gives us an ID for the download URL)
    pr_id = await storage.create_pr_card(
        district=req.district,
        taluka=req.taluka,
        village=req.village,
        survey_no=req.survey_no,
        survey_no_part1=req.survey_no_part1,
        mobile=req.mobile,
        property_uid=req.property_uid,
        property_uid_known=req.property_uid_known,
        record_of_right=req.record_of_right.value,
        language=req.language,
    )

    # Run scraper and wait
    result = await _do_scrape(pr_id, form_state, storage)

    # Build download URL from incoming request host
    base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/download/{pr_id}"

    status = result.get("status", "failed")

    pr_card = await storage.get_pr_card(pr_id)
    created_at = pr_card["created_at"] if pr_card else datetime.utcnow()

    return PRCardResponse(
        id=pr_id,
        status=PRCardStatus(status),
        district=req.district,
        taluka=req.taluka,
        village=req.village,
        survey_no=req.survey_no,
        created_at=created_at,
        error_message=result.get("error"),
        image_url=result.get("image_url"),
        download_url=download_url if status == "completed" else None,
        extracted_data=result.get("extracted_data"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Status / Download
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/status/{pr_id}", response_model=PRCardResponse)
async def get_pr_card_status(pr_id: str, request: Request):
    """Poll processing status of an async PR Card request."""
    storage = get_storage()
    pr_card = await storage.get_pr_card(pr_id)
    if not pr_card:
        raise HTTPException(status_code=404, detail="PR Card not found")

    base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/download/{pr_id}" if pr_card["status"] == "completed" else None

    return PRCardResponse(
        id=pr_card["id"],
        status=pr_card["status"],
        district=pr_card["district"],
        taluka=pr_card["taluka"],
        village=pr_card["village"],
        survey_no=pr_card["survey_no"],
        created_at=pr_card["created_at"],
        error_message=pr_card.get("error_message"),
        image_url=pr_card.get("image_url"),
        download_url=download_url,
        extracted_data=pr_card.get("extracted_data"),
    )


@router.get("/download/{pr_id}")
async def download_pr_card(pr_id: str):
    """Download the PR Card image for a completed request."""
    storage = get_storage()
    pr_card = await storage.get_pr_card(pr_id)
    if not pr_card:
        raise HTTPException(status_code=404, detail="PR Card not found")
    if pr_card["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"PR Card status: {pr_card['status']}")

    image = await storage.get_pr_card_image(pr_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found in storage")

    # Detect format from first bytes (JPEG = FF D8, PNG = 89 50)
    media_type = "image/jpeg" if image[:2] == b"\xff\xd8" else "image/png"
    ext = "jpg" if media_type == "image/jpeg" else "png"

    return Response(
        content=image,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=pr_card_{pr_id}.{ext}"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok", "service": "pr_card_scraper", "scraper": "playwright"}


# ─────────────────────────────────────────────────────────────────────────────
# Shared persistence helper
# ─────────────────────────────────────────────────────────────────────────────

async def _persist_result(storage: StorageService, pr_id: str, result: dict):
    """Save scraper result to the database."""
    status = result.get("status")

    if status == "completed":
        output_path = result.get("output_path")
        image_bytes = None
        if output_path and os.path.exists(output_path):
            image_bytes = await asyncio.to_thread(
                lambda: open(output_path, "rb").read()
            )
        if not image_bytes:
            image_bytes = result.get("image_bytes")

        await storage.update_pr_card(
            pr_id=pr_id,
            status="completed",
            image=image_bytes,
            image_url=result.get("image_url"),
            extracted_data=result.get("extracted_data"),
        )
        logger.info(f"PR Card {pr_id} completed — {output_path}")

    elif status == "captcha_required":
        await storage.update_pr_card(
            pr_id=pr_id,
            status="captcha_required",
            error_message=result.get("error", "CAPTCHA required"),
            captcha_image=result.get("captcha_image"),
        )
        logger.info(f"PR Card {pr_id} — manual CAPTCHA required")

    else:
        await storage.update_pr_card(
            pr_id=pr_id,
            status="failed",
            error_message=result.get("error", "Unknown error"),
        )
        logger.error(f"PR Card {pr_id} failed: {result.get('error')}")
