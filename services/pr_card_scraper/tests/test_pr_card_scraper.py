import asyncio
import json
from unittest.mock import AsyncMock, patch

from utils import setup_path

setup_path("pr_card_scraper")

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "data_extractor",
    "services/pr_card_scraper/services/data_extractor.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
LLMDataExtractor = mod.LLMDataExtractor

MOCK_LLM_RESPONSE = json.dumps(
    {
        "cts_no": "83",
        "area_sqm": 1525.10,
        "district": "parbhani",
    }
)


async def test_pr_card_scraper_flow():
    print("Testing PR Card Scraper (Data Extractor) Flow...")
    extractor = LLMDataExtractor(gemini_api_key="fake", openai_api_key="")

    print("- Testing extraction with mock Gemini response")
    with (
        patch.object(mod, "_prepare_image", return_value="fake-b64"),
        patch.object(extractor, "_gemini_extract", new_callable=AsyncMock) as mock_gemini,
    ):
        mock_gemini.return_value = json.loads(MOCK_LLM_RESPONSE)
        result = await extractor.extract(b"fake-image-bytes")
        print(f"  Extracted CTS No: {result.get('cts_no')}")
        assert result["cts_no"] == "83"


if __name__ == "__main__":
    asyncio.run(test_pr_card_scraper_flow())
