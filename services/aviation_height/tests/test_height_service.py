import asyncio
from unittest.mock import AsyncMock, patch

from utils import setup_path

setup_path("height_service")

from services.aviation_height.services.height_service import (  # noqa: E402
    HeightService,
    NOCASUnavailableError,
)


async def test_height_service_flow():
    print("Testing Height Service Flow...")
    svc = HeightService()

    # Test successful fetch
    real_result = {
        "lat": 18.9967,
        "lng": 72.8325,
        "max_height_m": 120.5,
        "max_floors": 40,
        "restriction_reason": "Airport proximity (Airport: Mumbai)",
        "nocas_reference": "N/A (Approximate)",
        "aai_zone": "Mumbai",
        "rl_datum_m": 135.5,
    }

    print("- Testing successful fetch (mocked)")
    with patch.object(svc, "_fetch_from_nocas", new_callable=AsyncMock, return_value=real_result):
        result = await svc.get_height(18.9967, 72.8325)
        assert result["max_height_m"] == 120.5
        assert result["is_real_data"] is True
        print(f"  Result: {result['max_height_m']}m")

    # Test retry and fail
    print("- Testing retry and failure (mocked)")
    with patch.object(svc, "_fetch_from_nocas", new_callable=AsyncMock, side_effect=[None, None]):
        try:
            await svc.get_height(18.9967, 72.8325)
            print("  FAILED: Should have raised NOCASUnavailableError")
        except NOCASUnavailableError:
            print("  SUCCESS: Raised NOCASUnavailableError after retries")


if __name__ == "__main__":
    asyncio.run(test_height_service_flow())
