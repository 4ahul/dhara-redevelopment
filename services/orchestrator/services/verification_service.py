import logging

import httpx
from fastapi import HTTPException, UploadFile

from ..core.config import settings
from .pmc_verification import verify_architect, verify_licensed_surveyor

logger = logging.getLogger(__name__)

ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
MAX_BYTES = 15 * 1024 * 1024  # 15 MB


class VerificationService:
    async def validate_file(self, file: UploadFile) -> tuple[bytes, str]:
        """Validate file size and type."""
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

    async def extract_registration(
        self, content: bytes, mime: str, filename: str, doc_type: str
    ) -> dict:
        """Call OCR service to extract registration number."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                endpoint = f"{settings.OCR_URL}/{doc_type}/extract-registration"
                resp = await client.post(
                    endpoint,
                    files={"file": (filename, content, mime)},
                    data={"strategy": "auto", "lang": "eng"},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.exception(f"OCR extraction failed for {doc_type}")
            raise HTTPException(status_code=502, detail=f"OCR service error: {e!s}") from e

    async def verify_licensed_surveyor_file(self, file: UploadFile) -> dict:
        """Process file and verify Licensed Surveyor."""
        content, mime = await self.validate_file(file)
        extraction = await self.extract_registration(
            content, mime, file.filename or "certificate", "ls"
        )

        if not extraction.get("ok"):
            return {"valid": False, **extraction}

        reg_no = extraction["registrationNumber"]
        result = await verify_licensed_surveyor(reg_no)

        return {
            **result,
            "extractedRegistrationNumber": reg_no,
            "usedOcr": extraction.get("usedOcr", False),
        }

    async def verify_architect_file(self, file: UploadFile) -> dict:
        """Process file and verify Architect."""
        content, mime = await self.validate_file(file)
        extraction = await self.extract_registration(
            content, mime, file.filename or "certificate", "architect"
        )

        if not extraction.get("ok"):
            return {"valid": False, **extraction}

        reg_no = extraction["registrationNumber"]
        result = await verify_architect(reg_no)

        return {
            **result,
            "extractedRegistrationNumber": reg_no,
            "usedOcr": extraction.get("usedOcr", False),
        }
