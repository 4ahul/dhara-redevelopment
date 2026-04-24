from fastapi import APIRouter
from services.ready_reckoner.schemas import PremiumRequest, PremiumResponse
from services.ready_reckoner.services.premium_service import premium_service
from dhara_shared.dhara_shared.dhara_common.schemas import InternalServiceResponse

router = APIRouter()

@router.post("/calculate", response_model=InternalServiceResponse)
async def get_premium_calculation(req: PremiumRequest):
    try:
        result = premium_service.calculate_premiums(req)
        return InternalServiceResponse(status="success", data=result)
    except Exception as e:
        return InternalServiceResponse(status="error", error=str(e))

