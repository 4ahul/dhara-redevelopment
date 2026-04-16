import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.unit
class TestHeightServiceRetry:

    @pytest.mark.asyncio
    async def test_returns_real_data_on_first_success(self):
        """When NOCAS responds on first try, return real data with metadata."""
        from services.height_service.services.height_service import HeightService

        svc = HeightService()
        real_result = {
            "lat": 18.9967, "lng": 72.8325,
            "max_height_m": 120.5, "max_floors": 40,
            "restriction_reason": "Airport proximity (Airport: Mumbai)",
            "nocas_reference": "N/A (Approximate)",
            "aai_zone": "Mumbai", "rl_datum_m": 135.5,
        }
        with patch.object(svc, "_fetch_from_nocas", new_callable=AsyncMock, return_value=real_result):
            result = await svc.get_height(18.9967, 72.8325)

        assert result["max_height_m"] == 120.5
        assert result["is_real_data"] is True
        assert result["data_source"] == "aai_nocas"
        assert result["attempt"] == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_and_succeeds(self):
        """When first attempt fails but second succeeds, return data with attempt=2."""
        from services.height_service.services.height_service import HeightService

        svc = HeightService()
        real_result = {
            "lat": 18.9967, "lng": 72.8325,
            "max_height_m": 120.5, "max_floors": 40,
            "restriction_reason": "Airport proximity",
            "nocas_reference": "N/A (Approximate)",
            "aai_zone": "Mumbai", "rl_datum_m": 135.5,
        }
        with patch.object(svc, "_fetch_from_nocas", new_callable=AsyncMock,
                          side_effect=[None, real_result]):
            result = await svc.get_height(18.9967, 72.8325)

        assert result["attempt"] == 2
        assert result["is_real_data"] is True

    @pytest.mark.asyncio
    async def test_raises_after_all_retries_exhausted(self):
        """When all 3 attempts fail, raise NOCASUnavailableError."""
        from services.height_service.services.height_service import (
            HeightService, NOCASUnavailableError,
        )

        svc = HeightService()
        with patch.object(svc, "_fetch_from_nocas", new_callable=AsyncMock,
                          side_effect=[None, None, None]):
            with pytest.raises(NOCASUnavailableError):
                await svc.get_height(18.9967, 72.8325)

    @pytest.mark.asyncio
    async def test_raises_on_exceptions(self):
        """When _fetch_from_nocas raises exceptions, still retries then raises."""
        from services.height_service.services.height_service import (
            HeightService, NOCASUnavailableError,
        )

        svc = HeightService()
        with patch.object(svc, "_fetch_from_nocas", new_callable=AsyncMock,
                          side_effect=Exception("browser crashed")):
            with pytest.raises(NOCASUnavailableError, match="browser crashed"):
                await svc.get_height(18.9967, 72.8325)

    def test_no_mock_response_method_exists(self):
        """Verify _mock_response is completely removed."""
        from services.height_service.services.height_service import HeightService
        assert not hasattr(HeightService, "_mock_response")
