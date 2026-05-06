from dhara_shared.schemas import InternalServiceResponse
from fastapi import APIRouter

from ..schemas import PremiumRequest
from ..services.premium_service import premium_service

router = APIRouter()


@router.post("/calculate", response_model=InternalServiceResponse)
async def get_premium_calculation(req: PremiumRequest):
    try:
        result = await premium_service.calculate_premiums(req)
        return InternalServiceResponse(status="success", data=result.model_dump())
    except Exception as e:
        return InternalServiceResponse(status="error", error=str(e))
