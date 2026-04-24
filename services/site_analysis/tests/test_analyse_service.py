import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.unit
class TestSiteAnalysisService:
    """Test suite for SiteAnalysisService"""

    @pytest.mark.asyncio
    async def test_analyse_success_with_mocked_geocode(self):
        """Test successful site analysis with mocked geocoding"""
        from services.site_analysis.services.analyse import SiteAnalysisService

        svc = SiteAnalysisService()

        mock_geocode = {
            "lat": 19.0133378,
            "lng": 72.8246606,
            "formatted_address": "Sanjay Society, Swatantryaveer Savarkar Rd, Century Bazaar, Prabhadevi, Mumbai, Maharashtra 400025, India",
            "area_type": "Predominantly Commercial",
            "nearby_landmarks": ["SyndicateBank Mumbai Prabhadevi Branch", "Marshalls Wallcoverings"],
            "place_id": "ChIJ7yeIUb7O5zsRR3GZw9zK2W4",
            "maps_url": "https://www.google.com/maps/search/?api=1&query=19.0133378,72.8246606&query_place_id=ChIJ7yeIUb7O5zsRR3GZw9zK2W4",
        }
        mock_zone = {"ward": "G/S", "zone": "R"}

        with patch.object(svc, "_geocode", new_callable=AsyncMock, return_value=mock_geocode), \
             patch.object(svc, "_query_mcgm_zone", new_callable=AsyncMock, return_value=mock_zone):
            result = await svc.analyse("Sanjay CHS, Prabhadevi, Mumbai")

        assert result["lat"] == 19.0133378
        assert result["lng"] == 72.8246606
        assert result["formatted_address"] == mock_geocode["formatted_address"]
        assert result["area_type"] == mock_geocode["area_type"]
        assert result["nearby_landmarks"] == mock_geocode["nearby_landmarks"]
        assert result["place_id"] == mock_geocode["place_id"]
        assert result["zone_inference"] == mock_zone["zone"]
        assert result["ward"] == mock_zone["ward"]
        assert result["zone_source"] == "mcgm_arcgis"

    @pytest.mark.asyncio
    async def test_analyse_fails_when_geocoding_fails(self):
        """Test that SiteAnalysisUnavailableError is raised when geocoding fails"""
        from services.site_analysis.services.analyse import (
            SiteAnalysisService, SiteAnalysisUnavailableError,
        )

        svc = SiteAnalysisService()

        with patch.object(svc, "_geocode", new_callable=AsyncMock, return_value=None):
            with pytest.raises(SiteAnalysisUnavailableError):
                await svc.analyse("nonexistent address xyz")

    @pytest.mark.asyncio
    async def test_analyse_returns_none_zone_when_mcgm_unavailable(self):
        """Test that zone_inference is None when MCGM queries fail"""
        from services.site_analysis.services.analyse import SiteAnalysisService

        svc = SiteAnalysisService()

        mock_geocode = {
            "lat": 19.0133378,
            "lng": 72.8246606,
            "formatted_address": "Sanjay Society, Swatantryaveer Savarkar Rd, Century Bazaar, Prabhadevi, Mumbai, Maharashtra 400025, India",
            "area_type": "Predominantly Commercial",
            "nearby_landmarks": ["SyndicateBank Mumbai Prabhadevi Branch", "Marshalls Wallcoverings"],
            "place_id": "ChIJ7yeIUb7O5zsRR3GZw9zK2W4",
            "maps_url": "https://www.google.com/maps/search/?api=1&query=19.0133378,72.8246606&query_place_id=ChIJ7yeIUb7O5zsRR3GZw9zK2W4",
        }

        with patch.object(svc, "_geocode", new_callable=AsyncMock, return_value=mock_geocode), \
             patch.object(svc, "_query_mcgm_zone", new_callable=AsyncMock, return_value=None):
            result = await svc.analyse("Sanjay CHS, Prabhadevi, Mumbai")

        assert result["zone_inference"] is None
        assert result["ward"] is None
        assert result["zone_source"] == "unavailable"

    def test_infer_area_type_function(self):
        """Test the infer_area_type helper function"""
        from services.site_analysis.services.analyse import infer_area_type

        # Test commercial area
        commercial_places = [
            {"name": "Shopping Mall", "types": ["store"]},
            {"name": "Bank of India", "types": ["bank"]},
            {"name": "Restaurant", "types": ["restaurant"]},
        ]
        assert infer_area_type(commercial_places) == "Predominantly Commercial"

        # Test residential area
        residential_places = [
            {"name": "Apartment Complex", "types": ["apartment"]},
            {"name": "Housing Society", "types": ["real_estate_agency"]},
            {"name": "Hostel", "types": ["lodging"]},
        ]
        assert infer_area_type(residential_places) == "Predominantly Residential"

        # Test mixed use - need both scores > 5
        mixed_places = []
        # Add 6 commercial places
        for i in range(6):
            mixed_places.append({"name": f"Shop {i}", "types": ["store"]})
        # Add 6 residential places
        for i in range(6):
            mixed_places.append({"name": f"Apartment {i}", "types": ["apartment"]})
        result = infer_area_type(mixed_places)
        assert "Mixed Use" in result

    def test_infer_area_type_empty_input(self):
        """Test infer_area_type with empty input"""
        from services.site_analysis.services.analyse import infer_area_type

        assert infer_area_type([]) == "Predominantly Residential"  # Default fallback

    def test_site_analysis_unavailable_error(self):
        """Test SiteAnalysisUnavailableError can be raised and caught"""
        from services.site_analysis.services.analyse import SiteAnalysisUnavailableError

        with pytest.raises(SiteAnalysisUnavailableError):
            raise SiteAnalysisUnavailableError("Test error")

        try:
            raise SiteAnalysisUnavailableError("Test error")
        except SiteAnalysisUnavailableError as e:
            assert str(e) == "Test error"

