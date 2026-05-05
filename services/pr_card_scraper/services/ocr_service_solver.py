import logging

import httpx

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import settings

logger = logging.getLogger(__name__)


class OCRServiceSolver:
    """Solver that uses the project's internal OCR service for CAPTCHAs."""

    def __init__(self):
        self.url = f"{settings.OCR_URL}/extract"

    async def solve(self, image_bytes: bytes) -> str | None:
        """
        Send CAPTCHA to internal OCR service.
        Request doc_type='captcha' (special mode for alphanumeric/case sensitivity).
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.url,
                    files={"file": ("captcha.png", image_bytes, "image/png")},
                    data={"doc_type": "captcha"},
                )
                resp.raise_for_status()
                data = resp.json()

                # The OCR service returns raw text in the 'raw' dict or society_age field for non-plan types
                text = data.get("raw", {}).get("text", "").strip()

                if text:
                    logger.info("Internal OCR Service CAPTCHA result: '%s'", text)
                    return text
        except Exception as e:
            logger.warning("Internal OCR Service CAPTCHA failed: %s", e)
        return None
