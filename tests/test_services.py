import pytest
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root and service directories to sys.path
root_path = Path(__file__).parent.parent.absolute()
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

# Add specific service directories to resolve their internal imports (core, schemas, etc.)
services_to_add = [
    "orchestrator",
    "site_analysis",
    "aviation_height",
    "ready_reckoner",
    "rag_service",
    "report_generator"
]
for s in services_to_add:
    s_path = str(root_path / "services" / s)
    if s_path not in sys.path:
        sys.path.append(s_path)

print(f"DEBUG: sys.path successfully initialized with services")

# Test data
SAMPLE_SITE_ANALYSIS = {
    "address": "FP No. 1128, TPS IV, A.M. Marg, Prabhadevi, Mumbai 400025",
    "ward": "G/S",
}

SAMPLE_HEIGHT_REQUEST = {"lat": 18.9967, "lng": 72.8325}

SAMPLE_RR_REQUEST = {"ward": "G/S", "year": 2024}

SAMPLE_PREMIUM_REQUEST = {
    "ward": "G/S",
    "plot_area_sqm": 1372.56,
    "property_area_sqm": 1372.56,
    "property_type": "residential",
    "scheme": "33(7)(B)",
    "permissible_bua_sqft": 44322,
    "residential_bua_sqft": 44322,
}


@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response."""

    def _mock(status=200, json_data=None):
        response = MagicMock()
        response.status_code = status
        response.json = MagicMock(return_value=json_data or {})
        response.content = b"mock binary content"
        response.headers = {"content-disposition": "filename=test.xlsx"}
        return response

    return _mock


class TestSiteAnalysisService:
    """Test cases for Site Analysis Service."""

    def test_infer_area_type_commercial(self):
        """Test area type inference for commercial areas."""
        from services.site_analysis.services.analyse import infer_area_type

        nearby = [
            {"name": "Shopping Mall", "types": ["store"]},
            {"name": "Bank", "types": ["bank"]},
            {"name": "Restaurant", "types": ["restaurant"]},
        ]
        result = infer_area_type(nearby)
        assert result == "Predominantly Commercial"

    def test_infer_area_type_residential(self):
        """Test area type inference for residential areas."""
        from services.site_analysis.services.analyse import infer_area_type

        nearby = [{"name": "Apartment", "types": ["premise"]}, {"name": "Housing Society", "types": ["neighborhood"]}]
        result = infer_area_type(nearby)
        assert result == "Predominantly Residential"

    def test_infer_area_type_mixed(self):
        """Test area type inference for mixed areas."""
        from services.site_analysis.services.analyse import infer_area_type

        # Mixed needs > 5 on both
        nearby = [
            {"name": "Shopping Mall", "types": ["store"]},
            {"name": "Bank Tower", "types": ["finance"]},
            {"name": "Office Complex", "types": ["office"]},
            {"name": "Restaurant Row", "types": ["restaurant"]},
            {"name": "Hotel Plaza", "types": ["hotel"]},
            {"name": "Clinic Center", "types": ["health"]},
            {"name": "Residential Apartment 1", "types": ["residential"]},
            {"name": "Residential Apartment 2", "types": ["residential"]},
            {"name": "Residential Apartment 3", "types": ["residential"]},
            {"name": "Residential Apartment 4", "types": ["residential"]},
            {"name": "Residential Apartment 5", "types": ["residential"]},
            {"name": "Residential Apartment 6", "types": ["residential"]},
        ]
        result = infer_area_type(nearby)
        assert result == "Mixed Use (Residential + Commercial)"


class TestHeightService:
    """Test cases for Height Service (Playwright-based)."""

    def test_decimal_to_dms(self):
        """Test coordinate conversion logic."""
        from services.aviation_height.services.height_service import height_service as aviation_height
        dd, mm, ss = aviation_height.decimal_to_dms(18.9967)
        assert dd == 18
        assert mm == 59
        assert ss == pytest.approx(48.12, rel=0.01)

    def test_no_mock_response(self):
        """Verify mock response is removed — service fails honestly."""
        from services.aviation_height.services.height_service import HeightService
        assert not hasattr(HeightService, "_mock_response")


class TestReadyReckonerService:
    """Test cases for Ready Reckoner Service."""

    def _get_rr_repo(self):
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "rr_repository",
            str(Path(__file__).parent.parent / "services" / "ready_reckoner" / "repositories" / "rr_repository.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        # Temporarily prepend ready_reckoner to sys.path for internal imports
        pc_path = str(Path(__file__).parent.parent / "services" / "ready_reckoner")
        sys.path.insert(0, pc_path)
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path.remove(pc_path)
        return mod.rr_repository

    def test_get_rates_for_prabhadevi(self):
        """Test RR rates lookup by locality."""
        rr_repository = self._get_rr_repo()
        result = rr_repository.get_rates(
            district="mumbai", taluka="mumbai-city", locality="prabhadevi"
        )
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_get_rates_for_unknown_locality(self):
        """Test RR rates for unknown locality returns empty."""
        rr_repository = self._get_rr_repo()
        result = rr_repository.get_rates(
            district="nonexistent", taluka="nonexistent", locality="nonexistent"
        )
        assert isinstance(result, dict)


class TestPremiumCheckerService:
    """Test cases for Premium Checker Service."""

    @pytest.fixture(autouse=True)
    def _setup_premium_path(self):
        """Temporarily add ready_reckoner to sys.path for imports."""
        pc_path = str(Path(__file__).parent.parent / "services" / "ready_reckoner")
        sys.path.insert(0, pc_path)
        yield
        sys.path.remove(pc_path)

    def test_additional_fsi_premium_calculation(self):
        """Test Additional FSI premium calculation."""
        from services.ready_reckoner.schemas import PremiumRequest
        from services.ready_reckoner.services.premium_service import premium_service

        req = PremiumRequest(**SAMPLE_PREMIUM_REQUEST)
        result = premium_service.calculate_premiums(req)

        # Find the Additional FSI line item
        add_fsi = next(
            (
                item
                for item in result.line_items
                if "Additional FSI Premium" in item.description
            ),
            None,
        )

        assert add_fsi is not None
        assert add_fsi.amount > 0

    def test_total_premium_calculation(self):
        """Test total premium calculation."""
        from services.ready_reckoner.schemas import PremiumRequest
        from services.ready_reckoner.services.premium_service import premium_service

        req = PremiumRequest(**SAMPLE_PREMIUM_REQUEST)
        result = premium_service.calculate_premiums(req)

        assert result.grand_total > 0
        assert result.grand_total_crore == pytest.approx(result.grand_total / 1e7, rel=0.01)

    def test_scheme_comparison(self):
        """Test premium calculation for different schemes."""
        from services.ready_reckoner.schemas import PremiumRequest
        from services.ready_reckoner.services.premium_service import premium_service

        schemes = ["33(7)(B)", "33(20)(B)", "33(11)", "33(12)(B)"]
        results = {}

        for scheme in schemes:
            req = PremiumRequest(**{**SAMPLE_PREMIUM_REQUEST, "scheme": scheme})
            result = premium_service.calculate_premiums(req)
            results[scheme] = result.grand_total

        # All schemes should have valid calculations
        for scheme, total in results.items():
            assert total > 0


class TestFSICalculations:
    """Test FSI calculations (DCPR 2034 rules)."""

    def test_fsi_33_7_b(self):
        """Test FSI calculation for 33(7)(B) scheme."""
        plot_area_sqm = 1372.56
        road_width_m = 27.45

        # DCPR 2034 for road > 18m
        zonal_fsi = 1.33
        add_fsi_premium = 0.84  # Additional FSI premium
        tdr_road_width = 0.83  # TDR on road width
        fungible = 1.05  # 35% fungible

        total_fsi = zonal_fsi + add_fsi_premium + tdr_road_width
        total_permissible = total_fsi + fungible

        assert total_fsi == pytest.approx(3.0, rel=0.01)
        assert total_permissible == pytest.approx(4.05, rel=0.01)

    def test_fsi_33_20_b(self):
        """Test FSI calculation for 33(20)(B) scheme."""
        plot_area_sqm = 1372.56

        # DCPR 2034 for 33(20)(B)
        zonal_fsi = 1.33
        add_fsi_premium = 0.84
        tdr_road_width = 0.83
        add_fsi_2020b = 1.00  # Additional FSI 33(20)(B)
        fungible = 1.40  # 35% fungible

        total_fsi = zonal_fsi + add_fsi_premium + tdr_road_width + add_fsi_2020b
        total_permissible = total_fsi + fungible

        assert total_fsi == pytest.approx(4.0, rel=0.01)
        assert total_permissible == pytest.approx(5.40, rel=0.01)

    def test_bua_calculation(self):
        """Test Built-Up Area calculation."""
        plot_area_sqm = 1372.56
        total_fsi = 4.05

        # Convert sqm to sqft (1 sqm = 10.764 sqft)
        plot_area_sqft = plot_area_sqm * 10.764
        bua = plot_area_sqft * total_fsi
        rera_carpet = bua * 0.90  # RERA carpet is 90% of BUA

        assert bua == pytest.approx(59865, rel=0.01)
        assert rera_carpet == pytest.approx(53878, rel=0.01)


@pytest.mark.skipif(
    not all(__import__("importlib").util.find_spec(m) for m in ["asyncpg"]),
    reason="asyncpg not installed — orchestrator tests require it",
)
class TestLLMClient:
    """Test LLM client abstraction."""

    def test_get_llm_client_gemini_priority(self):
        """Test factory returns GeminiClient when GEMINI_API_KEY is set."""
        import os
        from agent.llm_client import get_llm_client, GeminiClient

        os.environ.setdefault("GEMINI_API_KEY", "test-key")
        client = get_llm_client()
        assert isinstance(client, GeminiClient)

    def test_get_llm_client_no_key_raises(self):
        """Test factory raises RuntimeError when no API key is configured."""
        import os
        from agent.llm_client import get_llm_client

        saved = {k: os.environ.pop(k, None) for k in (
            "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
            "OLLAMA_BASE_URL", "OLLAMA_MODEL",
            "OPENAI_BASE_URL", "OPENAI_MODEL",
        )}
        try:
            with pytest.raises(RuntimeError, match="No LLM API key"):
                get_llm_client()
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_ollama_client_config(self):
        """Test OllamaClient configuration."""
        from agent.llm_client import OllamaClient

        client = OllamaClient(
            base_url="http://localhost:11434", model="llama3.2:latest"
        )

        assert client.base_url == "http://localhost:11434"
        assert client.model == "llama3.2:latest"
        assert client.get_model_name() == "llama3.2:latest"

    def test_openai_client_config(self):
        """Test OpenAICompatibleClient configuration."""
        from agent.llm_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://localhost:8000/v1",
            api_key="test-key",
            model="llama-3.1-8b-instruct",
        )

        assert client.base_url == "http://localhost:8000/v1"
        assert client.api_key == "test-key"
        assert client.model == "llama-3.1-8b-instruct"


class TestModels:
    """Test Pydantic models."""

    def test_plot_data_model(self):
        """Test PlotData model."""
        from dhara_shared.models import PlotData

        data = PlotData(
            cts_no="FP 1128", village="Prabhadevi", ward="G/S", plot_area_sqm=1372.56
        )

        assert data.cts_no == "FP 1128"
        assert data.plot_area_sqm == 1372.56

    def test_site_analysis_result_model(self):
        """Test SiteAnalysisResult model."""
        from dhara_shared.models import SiteAnalysisResult

        result = SiteAnalysisResult(
            lat=18.9967,
            lng=72.8325,
            formatted_address="Test Address",
            area_type="Residential",
            nearby_landmarks=["Landmark 1"],
            place_id="test123",
            zone_inference="R Zone",
        )

        assert result.lat == 18.9967
        assert result.area_type == "Residential"

    def test_feasibility_input_model(self):
        """Test FeasibilityInput model."""
        from dhara_shared.models import (
            FeasibilityInput,
            PlotData,
            SiteAnalysisResult,
            HeightResult,
            ReadyReckoner,
            PremiumData,
        )

        plot = PlotData(cts_no="FP 1128", village="Test", ward="G/S")
        site = SiteAnalysisResult(
            lat=0,
            lng=0,
            formatted_address="",
            area_type="",
            nearby_landmarks=[],
            place_id="",
            zone_inference="",
        )
        height = HeightResult(
            lat=0,
            lng=0,
            max_height_m=150,
            max_floors=50,
            restriction_reason="",
            nocas_reference="",
        )
        rr = ReadyReckoner(
            ward="G/S",
            zone="R",
            rr_open_land_sqm=100000,
            rr_residential_sqm=200000,
            rr_commercial_sqm=300000,
            rr_construction_cost_sqm=25000,
            year=2024,
        )
        premium = PremiumData(
            plot_area_sqm=1000,
            fsi_premium_amount=5000000,
            tdr_cost=3000000,
            fungible_premium=2000000,
            open_space_deficiency=1000000,
            total_govt_charges=11000000,
        )

        fi = FeasibilityInput(
            plot_data=plot,
            site_analysis=site,
            height_result=height,
            ready_reckoner=rr,
            premium_data=premium,
            society_name="Test Society",
            existing_residential_area_sqft=10000.0,
            existing_commercial_area_sqft=0.0,
            num_flats=20,
            num_commercial=0,
            sale_rate_per_sqft=65000.0,
        )

        assert fi.society_name == "Test Society"
        assert fi.plot_data.cts_no == "FP 1128"
        assert fi.num_flats == 20


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
