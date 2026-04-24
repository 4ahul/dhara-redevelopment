from fastapi import APIRouter
from schemas import PremiumRequest, PremiumResponse
from services.premium_service import premium_service

router = APIRouter()

@router.post("/calculate", response_model=PremiumResponse)
async def get_premium_calculation(req: PremiumRequest):
    return premium_service.calculate_premiums(req)
