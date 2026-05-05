import logging

from fastapi import APIRouter, Depends, File, UploadFile

from ...core.dependencies import require_pmc
from ...services.verification_service import VerificationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/verify", tags=["PMC Verification"], dependencies=[Depends(require_pmc)])


def get_verification_service() -> VerificationService:
    return VerificationService()


@router.post("/license-surveyor")
async def verify_license_surveyor(
    file: UploadFile = File(...), service: VerificationService = Depends(get_verification_service)
):
    """Verify Licensed Surveyor certificate via OCR and MCGM portal."""
    return await service.verify_licensed_surveyor_file(file)


@router.post("/architect")
async def verify_architect(
    file: UploadFile = File(...), service: VerificationService = Depends(get_verification_service)
):
    """Verify Architect certificate via OCR and COA portal."""
    return await service.verify_architect_file(file)
