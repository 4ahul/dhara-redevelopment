import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.unit
class TestSiteAnalysisZone:

    @pytest.mark.asyncio
    async def test_returns_arcgis_zone_when_available(self):
        """When MCGM ArcGIS returns zone data, use it instead of heuristic."""
        from services.site_analysis.services.analyse import SiteAnalysisService

        svc = SiteAnalysisService()

        mock_geocode = {
            "lat": 18.9967, "lng": 72.8325,
            "formatted_address": "Prabhadevi, Mumbai",
            "area_type": "Mixed Use (Residential + Commercial)",
            "nearby_landmarks": ["Siddhivinayak Temple"],
            "place_id": "test_id",
            "maps_url": "https://maps.google.com",
        }
        mock_zone = {"ward": "G/S", "zone": "Residential (R)"}

        with patch.object(svc, "_geocode", new_callable=AsyncMock, return_value=mock_geocode), \
             patch.object(svc, "_query_mcgm_zone", new_callable=AsyncMock, return_value=mock_zone):
            result = await svc.analyse("Prabhadevi, Mumbai")

        assert result["zone_inference"] == "Residential (R)"
        assert result["ward"] == "G/S"
        assert result["zone_source"] == "mcgm_arcgis"

    @pytest.mark.asyncio
    async def test_returns_null_zone_when_arcgis_unavailable(self):
        """When MCGM ArcGIS fails, zone_inference is None, not a heuristic guess."""
        from services.site_analysis.services.analyse import SiteAnalysisService

        svc = SiteAnalysisService()

        mock_geocode = {
            "lat": 18.9967, "lng": 72.8325,
            "formatted_address": "Prabhadevi, Mumbai",
            "area_type": "Mixed Use (Residential + Commercial)",
            "nearby_landmarks": ["Siddhivinayak Temple"],
            "place_id": "test_id",
            "maps_url": "https://maps.google.com",
        }

        with patch.object(svc, "_geocode", new_callable=AsyncMock, return_value=mock_geocode), \
             patch.object(svc, "_query_mcgm_zone", new_callable=AsyncMock, return_value=None):
            result = await svc.analyse("Prabhadevi, Mumbai")

        assert result["zone_inference"] is None
        assert result["ward"] is None
        assert result["zone_source"] == "unavailable"

    @pytest.mark.asyncio
    async def test_raises_when_geocoding_fails(self):
        """When both Google Maps and SerpApi fail, raise error instead of returning mock."""
        from services.site_analysis.services.analyse import (
            SiteAnalysisService, SiteAnalysisUnavailableError,
        )

        svc = SiteAnalysisService()

        with patch.object(svc, "_geocode", new_callable=AsyncMock, return_value=None):
            with pytest.raises(SiteAnalysisUnavailableError):
                await svc.analyse("nonexistent address xyz")

    def test_no_infer_zone_function(self):
        """Verify infer_zone heuristic function is removed."""
        import services.site_analysis.services.analyse as mod
        assert not hasattr(mod, "infer_zone")

    def test_no_mock_response_method(self):
        """Verify _mock_response is removed."""
        from services.site_analysis.services.analyse import SiteAnalysisService
        assert not hasattr(SiteAnalysisService, "_mock_response")
