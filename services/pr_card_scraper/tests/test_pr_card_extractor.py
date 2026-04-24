import importlib
import json
import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _import_data_extractor():
    """Import data_extractor module directly, bypassing the package __init__.py
    which pulls in browser/playwright dependencies not needed for unit tests."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "data_extractor",
        "services/pr_card_scraper/services/data_extractor.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _import_data_extractor()
LLMDataExtractor = _mod.LLMDataExtractor

# Simulated LLM JSON response for a PR card
MOCK_LLM_RESPONSE = json.dumps({
    "property_uid": "807780274492",
    "village_patti": "kharbauda",
    "taluka": "purna",
    "district": "parbhani",
    "cts_no": "83",
    "sheet_number": None,
    "plot_number": "42",
    "area_sqm": 1525.10,
    "tenure": "freehold",
    "assessment": None,
    "survey_year": "2022",
    "holders": [{"name": "maroti kasipc", "share": None}],
    "encumbrances": None,
    "other_remarks": None,
    "transactions": []
})

# Patch target for _prepare_image in the loaded module
_PREPARE_IMAGE_PATH = f"{_mod.__name__}._prepare_image"


@pytest.mark.unit
class TestLLMDataExtractor:

    @pytest.mark.asyncio
    async def test_extract_returns_structured_data_from_gemini(self):
        """When Gemini returns valid JSON, extract() returns parsed dict with metadata."""
        extractor = LLMDataExtractor(
            gemini_api_key="fake-key", openai_api_key=""
        )

        with patch.object(_mod, "_prepare_image", return_value="fake-b64"), \
             patch.object(extractor, "_gemini_extract", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = json.loads(MOCK_LLM_RESPONSE)
            result = await extractor.extract(b"fake-image-bytes")

        assert result["cts_no"] == "83"
        assert result["area_sqm"] == 1525.10
        assert result["district"] == "parbhani"
        assert result["extraction_source"] == "gemini-2.5-flash"
        assert result["extraction_confidence"] in ("high", "medium", "low")

    @pytest.mark.asyncio
    async def test_extract_falls_back_to_openai(self):
        """When Gemini fails, extract() tries OpenAI."""
        extractor = LLMDataExtractor(
            gemini_api_key="fake-key", openai_api_key="fake-openai-key"
        )

        with patch.object(_mod, "_prepare_image", return_value="fake-b64"), \
             patch.object(extractor, "_gemini_extract", new_callable=AsyncMock) as mock_g, \
             patch.object(extractor, "_openai_extract", new_callable=AsyncMock) as mock_o:
            mock_g.return_value = None  # Gemini fails
            mock_o.return_value = json.loads(MOCK_LLM_RESPONSE)
            result = await extractor.extract(b"fake-image-bytes")

        assert result["cts_no"] == "83"
        assert result["extraction_source"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_extract_returns_empty_when_no_api_keys(self):
        """When no API keys are configured, extract() returns empty dict."""
        extractor = LLMDataExtractor(gemini_api_key="", openai_api_key="")
        with patch.object(_mod, "_prepare_image", return_value="fake-b64"):
            result = await extractor.extract(b"fake-image-bytes")
        assert result == {}

    @pytest.mark.asyncio
    async def test_confidence_is_high_when_key_fields_present(self):
        """Confidence is 'high' when cts_no AND area_sqm are present."""
        extractor = LLMDataExtractor(gemini_api_key="fake", openai_api_key="")
        parsed = json.loads(MOCK_LLM_RESPONSE)
        with patch.object(_mod, "_prepare_image", return_value="fake-b64"), \
             patch.object(extractor, "_gemini_extract", new_callable=AsyncMock, return_value=parsed):
            result = await extractor.extract(b"fake-image-bytes")
        assert result["extraction_confidence"] == "high"

    @pytest.mark.asyncio
    async def test_confidence_is_low_when_key_fields_missing(self):
        """Confidence is 'low' when both cts_no AND area_sqm are missing."""
        extractor = LLMDataExtractor(gemini_api_key="fake", openai_api_key="")
        parsed = {"cts_no": None, "area_sqm": None, "district": "pune"}
        with patch.object(_mod, "_prepare_image", return_value="fake-b64"), \
             patch.object(extractor, "_gemini_extract", new_callable=AsyncMock, return_value=parsed):
            result = await extractor.extract(b"fake-image-bytes")
        assert result["extraction_confidence"] == "low"

