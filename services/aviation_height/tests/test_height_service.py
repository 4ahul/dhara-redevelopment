import asyncio
from unittest.mock import AsyncMock, patch

from utils import setup_path

setup_path("height_service")

import contextlib

from services.aviation_height.services.height_service import (
    HeightService,
    NOCASUnavailableError,
)


async def test_height_service_flow():
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

    with patch.object(svc, "_fetch_from_nocas", new_callable=AsyncMock, return_value=real_result):
        result = await svc.get_height(18.9967, 72.8325)
        assert result["max_height_m"] == 120.5
        assert result["is_real_data"] is True

    # Test retry and fail
    with (
        patch.object(svc, "_fetch_from_nocas", new_callable=AsyncMock, side_effect=[None, None]),
        contextlib.suppress(NOCASUnavailableError),
    ):
        await svc.get_height(18.9967, 72.8325)


if __name__ == "__main__":
    asyncio.run(test_height_service_flow())
