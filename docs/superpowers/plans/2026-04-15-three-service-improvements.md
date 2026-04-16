# Three-Service Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-based OCR to PR card scraper, remove mock data from height service (fail honestly with retries), and replace heuristic zone inference with real MCGM ArcGIS data in site analysis.

**Architecture:** Each service is an independent FastAPI microservice. Changes are isolated per service — no cross-service dependencies. The PR card extractor reuses the existing Gemini/GPT-4o LLM Vision pattern. Height service adds retry logic and raises on failure. Site analysis adds a lightweight ArcGIS spatial query using the same MCGM endpoint as dp_report_service.

**Tech Stack:** Python, FastAPI, httpx, Pydantic, Playwright (height_service), Google Generative AI API, OpenAI API, Pillow, pytest, pytest-asyncio

---

## File Structure

### PR Card Scraper
- **Modify:** `services/pr_card_scraper/services/data_extractor.py` — replace stub with LLM vision extractor
- **Modify:** `services/pr_card_scraper/services/browser/__init__.py:177` — make extract call async
- **Create:** `tests/test_pr_card_extractor.py` — unit tests for extraction logic

### Height Service
- **Modify:** `services/height_service/services/height_service.py` — add retry loop, remove mock, add exception
- **Modify:** `services/height_service/schemas/__init__.py` — add new response fields
- **Modify:** `services/height_service/routers/height_router.py` — handle 503
- **Create:** `tests/test_height_service.py` — unit tests for retry and failure behavior

### Site Analysis
- **Modify:** `services/site_analysis/services/analyse.py` — add ArcGIS query, remove infer_zone, remove mock
- **Modify:** `services/site_analysis/schemas/__init__.py` — add ward, zone_source, make zone_inference nullable
- **Modify:** `services/site_analysis/routers/site_router.py` — handle 503
- **Create:** `tests/test_site_analysis.py` — unit tests for zone query and failure behavior

---

## Task 1: PR Card Scraper — LLM Data Extractor

**Files:**
- Modify: `services/pr_card_scraper/services/data_extractor.py`
- Modify: `services/pr_card_scraper/services/browser/__init__.py:177`
- Create: `tests/test_pr_card_extractor.py`

- [ ] **Step 1: Write failing test for LLM extraction**

Create `tests/test_pr_card_extractor.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock, patch

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


@pytest.mark.unit
class TestLLMDataExtractor:

    @pytest.mark.asyncio
    async def test_extract_returns_structured_data_from_gemini(self):
        """When Gemini returns valid JSON, extract() returns parsed dict with metadata."""
        from services.pr_card_scraper.services.data_extractor import LLMDataExtractor

        extractor = LLMDataExtractor(
            gemini_api_key="fake-key", openai_api_key=""
        )

        with patch.object(extractor, "_gemini_extract", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = json.loads(MOCK_LLM_RESPONSE)
            result = await extractor.extract(b"fake-image-bytes")

        assert result["cts_no"] == "83"
        assert result["area_sqm"] == 1525.10
        assert result["district"] == "parbhani"
        assert result["extraction_source"] == "gemini-2.0-flash"
        assert result["extraction_confidence"] in ("high", "medium", "low")

    @pytest.mark.asyncio
    async def test_extract_falls_back_to_openai(self):
        """When Gemini fails, extract() tries OpenAI."""
        from services.pr_card_scraper.services.data_extractor import LLMDataExtractor

        extractor = LLMDataExtractor(
            gemini_api_key="fake-key", openai_api_key="fake-openai-key"
        )

        with patch.object(extractor, "_gemini_extract", new_callable=AsyncMock) as mock_g, \
             patch.object(extractor, "_openai_extract", new_callable=AsyncMock) as mock_o:
            mock_g.return_value = None  # Gemini fails
            mock_o.return_value = json.loads(MOCK_LLM_RESPONSE)
            result = await extractor.extract(b"fake-image-bytes")

        assert result["cts_no"] == "83"
        assert result["extraction_source"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_extract_returns_empty_when_no_api_keys(self):
        """When no API keys are configured, extract() returns empty dict."""
        from services.pr_card_scraper.services.data_extractor import LLMDataExtractor

        extractor = LLMDataExtractor(gemini_api_key="", openai_api_key="")
        result = await extractor.extract(b"fake-image-bytes")
        assert result == {}

    @pytest.mark.asyncio
    async def test_confidence_is_high_when_key_fields_present(self):
        """Confidence is 'high' when cts_no AND area_sqm are present."""
        from services.pr_card_scraper.services.data_extractor import LLMDataExtractor

        extractor = LLMDataExtractor(gemini_api_key="fake", openai_api_key="")
        parsed = json.loads(MOCK_LLM_RESPONSE)
        with patch.object(extractor, "_gemini_extract", new_callable=AsyncMock, return_value=parsed):
            result = await extractor.extract(b"fake-image-bytes")
        assert result["extraction_confidence"] == "high"

    @pytest.mark.asyncio
    async def test_confidence_is_low_when_key_fields_missing(self):
        """Confidence is 'low' when both cts_no AND area_sqm are missing."""
        from services.pr_card_scraper.services.data_extractor import LLMDataExtractor

        extractor = LLMDataExtractor(gemini_api_key="fake", openai_api_key="")
        parsed = {"cts_no": None, "area_sqm": None, "district": "pune"}
        with patch.object(extractor, "_gemini_extract", new_callable=AsyncMock, return_value=parsed):
            result = await extractor.extract(b"fake-image-bytes")
        assert result["extraction_confidence"] == "low"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/Admin/Documents/Projects/redevelopment-ai && python -m pytest tests/test_pr_card_extractor.py -v`
Expected: FAIL — `ImportError: cannot import name 'LLMDataExtractor'`

- [ ] **Step 3: Implement LLMDataExtractor**

Replace contents of `services/pr_card_scraper/services/data_extractor.py`:

```python
"""
LLM Vision PR Card Data Extractor
Gemini 2.0 Flash (primary) -> GPT-4o (fallback).
Extracts structured fields from Property Card images.
"""

import base64
import io
import json
import logging
import os
import re
from typing import Optional

import httpx
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)

_PROMPT = """You are a document data extractor for Indian government Property Cards (PR Cards) from the Maharashtra Mahabhumi portal.

Extract ALL fields from this Property Card image into the following JSON structure.
If a field is not visible or unreadable, use null.

{
  "property_uid": "string or null",
  "village_patti": "string or null",
  "taluka": "string or null",
  "district": "string or null",
  "cts_no": "string or null",
  "sheet_number": "string or null",
  "plot_number": "string or null",
  "area_sqm": number or null,
  "tenure": "string or null",
  "assessment": "string or null",
  "survey_year": "string or null",
  "holders": [{"name": "string", "share": "string or null"}],
  "encumbrances": "string or null",
  "other_remarks": "string or null",
  "transactions": [{"date": "string", "transaction_type": "string", "vol_no": "string", "new_holder": "string"}]
}

Reply with ONLY valid JSON. No markdown, no explanation, no code fences."""


def _prepare_image(image_bytes: bytes) -> str:
    """Enlarge 2x + boost contrast -> base64 PNG. Helps LLMs read document text."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _parse_json_response(text: str) -> Optional[dict]:
    """Parse LLM response as JSON, with fallback for markdown-wrapped responses."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _compute_confidence(data: dict) -> str:
    """Compute extraction confidence based on key fields."""
    has_cts = data.get("cts_no") is not None
    has_area = data.get("area_sqm") is not None
    has_holders = bool(data.get("holders"))

    if has_cts and has_area:
        return "high"
    elif has_cts or has_area or has_holders:
        return "medium"
    return "low"


def _validate_area(data: dict) -> dict:
    """Validate and clean area_sqm field."""
    area = data.get("area_sqm")
    if area is not None:
        try:
            area = float(area)
            if not (0.1 <= area <= 100000):
                logger.warning("area_sqm out of range (%.2f), setting to null", area)
                data["area_sqm"] = None
            else:
                data["area_sqm"] = area
        except (ValueError, TypeError):
            data["area_sqm"] = None
    return data


class LLMDataExtractor:
    """Extract structured data from PR card images using LLM Vision."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
    ):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.openai_base_url = (
            openai_base_url
            or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )

    async def extract(self, image_bytes: bytes) -> dict:
        """
        Extract structured data from PR card image.
        Gemini Flash (primary) -> GPT-4o (fallback).
        Returns parsed dict with metadata, or empty dict on total failure.
        """
        if not self.gemini_api_key and not self.openai_api_key:
            logger.warning("No LLM API keys configured for PR card extraction")
            return {}

        b64 = _prepare_image(image_bytes)

        # Try Gemini first
        if self.gemini_api_key:
            result = await self._gemini_extract(b64)
            if result:
                result = _validate_area(result)
                result["extraction_confidence"] = _compute_confidence(result)
                result["extraction_source"] = "gemini-2.0-flash"
                return result

        # Fallback to GPT-4o
        if self.openai_api_key:
            result = await self._openai_extract(b64)
            if result:
                result = _validate_area(result)
                result["extraction_confidence"] = _compute_confidence(result)
                result["extraction_source"] = "gpt-4o"
                return result

        logger.warning("All LLM extraction attempts failed")
        return {}

    async def _gemini_extract(self, b64_image: str) -> Optional[dict]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": _PROMPT},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": 1024, "temperature": 0},
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            parsed = _parse_json_response(text)
            if parsed:
                logger.info("Gemini PR card extraction succeeded")
                return parsed
            logger.warning("Gemini returned unparseable response: %s", text[:200])
        except Exception as e:
            logger.warning("Gemini PR card extraction failed: %s", e)
        return None

    async def _openai_extract(self, b64_image: str) -> Optional[dict]:
        url = f"{self.openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a document data extractor for Indian government Property Cards. Always respond with only valid JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_image}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            "max_tokens": 1024,
            "temperature": 0,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, json=payload, headers=headers, timeout=15.0
                )
                resp.raise_for_status()
                data = resp.json()
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            parsed = _parse_json_response(text)
            if parsed:
                logger.info("OpenAI PR card extraction succeeded")
                return parsed
            logger.warning("OpenAI returned unparseable response: %s", text[:200])
        except Exception as e:
            logger.warning("OpenAI PR card extraction failed: %s", e)
        return None


# Backward-compatible alias — old code imports DataExtractor
DataExtractor = LLMDataExtractor
```

- [ ] **Step 4: Update browser/__init__.py to call extract() as async**

In `services/pr_card_scraper/services/browser/__init__.py`, change line 177 from:

```python
            extracted_data = self.data_extractor.extract(image_bytes)
```

to:

```python
            extracted_data = await self.data_extractor.extract(image_bytes)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/Admin/Documents/Projects/redevelopment-ai && python -m pytest tests/test_pr_card_extractor.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/pr_card_scraper/services/data_extractor.py services/pr_card_scraper/services/browser/__init__.py tests/test_pr_card_extractor.py
git commit -m "feat(pr-card): add LLM vision OCR to extract structured data from PR card images"
```

---

## Task 2: Height Service — Remove Mock, Add Retry, Fail Honestly

**Files:**
- Modify: `services/height_service/services/height_service.py`
- Modify: `services/height_service/schemas/__init__.py`
- Modify: `services/height_service/routers/height_router.py`
- Create: `tests/test_height_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_height_service.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Admin/Documents/Projects/redevelopment-ai && python -m pytest tests/test_height_service.py -v`
Expected: FAIL — `cannot import name 'NOCASUnavailableError'`, `_fetch_from_nocas` not found

- [ ] **Step 3: Update schema with new fields**

Replace `services/height_service/schemas/__init__.py`:

```python
from pydantic import BaseModel
from typing import Optional


class HeightRequest(BaseModel):
    lat: float
    lng: float
    site_elevation: Optional[float] = 0.0


class HeightResponse(BaseModel):
    lat: float
    lng: float
    max_height_m: float
    max_floors: int
    restriction_reason: str
    nocas_reference: str
    aai_zone: str
    rl_datum_m: float
    is_real_data: bool = True
    data_source: str = "aai_nocas"
    attempt: int = 1
```

- [ ] **Step 4: Rewrite height_service.py with retry logic and no mock**

Replace `services/height_service/services/height_service.py`:

```python
import asyncio
import logging
import re
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)


class NOCASUnavailableError(Exception):
    """Raised when AAI NOCAS cannot be reached after retries."""
    pass


class HeightService:
    """Service to interact with AAI NOCAS Map Page to get permissible height."""

    def __init__(self):
        self.url = "https://nocas2.aai.aero/nocas/MapPage.html"
        self.stealth = Stealth()

    def decimal_to_dms(self, decimal: float) -> tuple:
        """Convert decimal degrees to DD, MM, SS."""
        abs_val = abs(decimal)
        dd = int(abs_val)
        mm_decimal = (abs_val - dd) * 60
        mm = int(mm_decimal)
        ss = round((mm_decimal - mm) * 60, 2)
        return dd, mm, ss

    async def get_height(
        self, lat: float, lng: float, site_elevation: float = 0.0
    ) -> Dict[str, Any]:
        """
        Get permissible height with retry logic. Never returns mock data.
        Raises NOCASUnavailableError if all attempts fail.
        """
        last_error = None
        for attempt in range(3):
            try:
                result = await self._fetch_from_nocas(lat, lng, site_elevation)
                if result:
                    result["is_real_data"] = True
                    result["data_source"] = "aai_nocas"
                    result["attempt"] = attempt + 1
                    return result
                last_error = "NOCAS returned no result"
            except Exception as e:
                last_error = str(e)
                logger.warning("NOCAS attempt %d/3 failed: %s", attempt + 1, e)

            if attempt < 2:
                await asyncio.sleep(2)

        raise NOCASUnavailableError(
            f"NOCAS unavailable after 3 attempts. Last error: {last_error}"
        )

    async def _fetch_from_nocas(
        self, lat: float, lng: float, site_elevation: float
    ) -> Optional[Dict[str, Any]]:
        """Single attempt to fetch height from NOCAS. Returns dict or None."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()
                await self.stealth.apply_stealth_async(page)

                page.on(
                    "console",
                    lambda msg: logger.info(f"BROWSER CONSOLE: {msg.type} {msg.text}"),
                )

                await page.add_init_script("""
                    window.captured_alerts = [];
                    let _jAlert = undefined;
                    Object.defineProperty(window, 'jAlert', {
                        get: function() { return _jAlert; },
                        set: function(newVal) {
                            _jAlert = function(msg, title, callback) {
                                window.captured_alerts.push({msg: msg});
                                console.log('NOCAS ALERT: ' + msg);
                                if (typeof callback === 'function') callback(true);
                            };
                        },
                        configurable: true
                    });
                    window.alert = function(msg) {
                        window.captured_alerts.push({msg: msg});
                        console.log('NOCAS standard ALERT: ' + msg);
                    };
                """)

                logger.info(f"Loading NOCAS page for {lat}, {lng}")
                await page.goto(self.url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(5000)

                # Clean up overlays
                await page.evaluate("""
                    const overlays = ['popup_overlay', 'popup_container', 'terms_condition', 'loader'];
                    overlays.forEach(id => {
                        const el = document.getElementById(id);
                        if (el) el.style.display = 'none';
                    });
                """)

                # Convert coords to DMS
                lat_d, lat_m, lat_s = self.decimal_to_dms(lat)
                lng_d, lng_m, lng_s = self.decimal_to_dms(lng)

                # Fill the form
                await page.fill("#dy", str(lat_d))
                await page.fill("#my", str(lat_m))
                await page.fill("#sy", str(lat_s))
                await page.fill("#dx", str(lng_d))
                await page.fill("#mx", str(lng_m))
                await page.fill("#sx", str(lng_s))
                await page.fill("#site_elevation", str(site_elevation))

                # Trigger via JS functions
                logger.info("Calling addPoint and onclickApprox via evaluate...")
                await page.evaluate("""
                    if (typeof addPoint !== 'undefined') addPoint();
                    if (typeof onclickApprox !== 'undefined') {
                        onclickApprox();
                        const btnOK = document.getElementById("btnOK");
                        if (btnOK) btnOK.click();
                    }
                """)

                # Wait for result
                logger.info("Waiting for result...")
                max_wait = 45
                result_text = None
                for _ in range(max_wait):
                    alerts = await page.evaluate("window.captured_alerts")
                    if alerts:
                        for alert in alerts:
                            msg = alert["msg"]
                            if "Approximate Permissible Top Elevation" in msg:
                                result_text = msg
                                break
                            if (
                                "cannot be determined" in msg
                                or "try later" in msg.lower()
                            ):
                                logger.warning(f"NOCAS reported error: {msg}")
                        if result_text:
                            break
                    await asyncio.sleep(1)

                if result_text:
                    match = re.search(r"Elevation:\s*([\d\.]+)", result_text)
                    if match:
                        max_height_amsl = float(match.group(1))
                        max_height_agl = max_height_amsl - site_elevation
                        airport_name = (
                            await page.evaluate(
                                "sessionStorage.getItem('Remarks')"
                            )
                            or "Unknown"
                        )

                        return {
                            "lat": lat,
                            "lng": lng,
                            "max_height_m": round(max_height_agl, 2),
                            "max_floors": int(max_height_agl // 3),
                            "restriction_reason": f"Airport proximity (Airport: {airport_name})",
                            "nocas_reference": "N/A (Approximate)",
                            "aai_zone": airport_name,
                            "rl_datum_m": max_height_amsl,
                        }

                logger.warning("No result from NOCAS on this attempt")
                return None

            finally:
                await browser.close()


height_service = HeightService()
```

- [ ] **Step 5: Update router to handle NOCASUnavailableError as 503**

Replace `services/height_service/routers/height_router.py`:

```python
from fastapi import APIRouter, HTTPException
from schemas import HeightRequest, HeightResponse
from services.height_service import height_service, NOCASUnavailableError
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Height"])


@router.post("/check-height", response_model=HeightResponse)
async def get_permissible_height(request: HeightRequest):
    """
    Get permissible building height from NOCAS for given coordinates.
    Returns 503 if NOCAS is unavailable after retries.
    """
    logger.info(f"Height request for lat={request.lat}, lng={request.lng}")
    try:
        result = await height_service.get_height(
            lat=request.lat,
            lng=request.lng,
            site_elevation=request.site_elevation or 0.0,
        )
        return HeightResponse(**result)
    except NOCASUnavailableError as e:
        logger.error(f"NOCAS unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "nocas_unavailable",
                "message": str(e),
                "suggestion": "Retry later or provide height data manually",
            },
        )
    except Exception as e:
        logger.error(f"Error in height router: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd C:/Users/Admin/Documents/Projects/redevelopment-ai && python -m pytest tests/test_height_service.py -v`
Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add services/height_service/services/height_service.py services/height_service/schemas/__init__.py services/height_service/routers/height_router.py tests/test_height_service.py
git commit -m "feat(height): remove mock data, add retry logic, fail with 503 when NOCAS unavailable"
```

---

## Task 3: Site Analysis — Replace Heuristic Zone with MCGM ArcGIS Query

**Files:**
- Modify: `services/site_analysis/services/analyse.py`
- Modify: `services/site_analysis/schemas/__init__.py`
- Modify: `services/site_analysis/routers/site_router.py`
- Create: `tests/test_site_analysis.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_site_analysis.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Admin/Documents/Projects/redevelopment-ai && python -m pytest tests/test_site_analysis.py -v`
Expected: FAIL — `cannot import name 'SiteAnalysisUnavailableError'`, `_geocode` not found

- [ ] **Step 3: Update schema**

Replace `services/site_analysis/schemas/__init__.py`:

```python
from pydantic import BaseModel
from typing import Optional


class SiteAnalysisRequest(BaseModel):
    address: str
    ward: Optional[str] = None
    plot_no: Optional[str] = None


class SiteAnalysisResponse(BaseModel):
    lat: float
    lng: float
    formatted_address: str
    area_type: str
    nearby_landmarks: list[str]
    place_id: str
    zone_inference: Optional[str] = None
    ward: Optional[str] = None
    zone_source: str = "unavailable"
    maps_url: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    step: int
```

- [ ] **Step 4: Rewrite analyse.py — add ArcGIS query, remove heuristics and mock**

Replace `services/site_analysis/services/analyse.py`:

```python
import asyncio
import functools
import json
import logging
import math
from typing import Optional

import googlemaps
import httpx

from core import settings

logger = logging.getLogger(__name__)

MCGM_PORTAL_URL = "https://mcgm.maps.arcgis.com"

# Fields to look for in MCGM zone layers
_ZONE_FIELDS = {"ZONE_CODE", "ZONE", "LANDUSE", "LAND_USE", "DP_ZONE", "ZONING"}
_WARD_FIELDS = {"WARD", "WARD_NAME", "WARD_NO", "WARD_CODE"}


class SiteAnalysisUnavailableError(Exception):
    """Raised when geocoding fails entirely."""
    pass


def _wgs84_to_web_mercator(lng: float, lat: float):
    """Convert WGS84 (lng, lat) to Web Mercator (x, y) in metres."""
    R = 6378137.0
    x = R * math.radians(lng)
    y = R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def _pick(up: dict, keys: set) -> Optional[str]:
    """Pick first non-empty value matching any of the given keys."""
    for k in keys:
        v = up.get(k)
        if v is not None and str(v).strip() not in ("", "None", "null"):
            return str(v).strip()
    return None


def infer_area_type(nearby: list) -> str:
    """Infer area type from nearby places."""
    commercial_keywords = {
        "shopping", "mall", "store", "bank", "restaurant", "cafe",
        "office", "hotel", "hospital", "clinic", "pharmacy", "gym", "finance",
    }
    residential_keywords = {
        "residential", "apartment", "housing", "society", "hostel", "pg",
    }

    commercial_score = 0
    residential_score = 0

    for place in nearby:
        name = place.get("name", "").lower()
        types = place.get("types", [])

        for kw in commercial_keywords:
            if kw in name:
                commercial_score += 1
                break
        for kw in residential_keywords:
            if kw in name:
                residential_score += 1
                break

        if any(t in types for t in ["store", "restaurant", "bank", "office", "health"]):
            commercial_score += 1
        if any(t in types for t in ["premise", "neighborhood", "real_estate_agency"]):
            residential_score += 0.5

    if commercial_score > 5 and residential_score > 5:
        return "Mixed Use (Residential + Commercial)"
    elif commercial_score > residential_score:
        return "Predominantly Commercial"
    else:
        return "Predominantly Residential"


class SiteAnalysisService:
    """Site analysis using Google Maps API + MCGM ArcGIS for zone data."""

    def __init__(self):
        self.gmaps = None
        if settings.GOOGLE_MAPS_API_KEY:
            self.gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
        self._zone_layer_url: Optional[str] = None

    async def analyse(
        self, address: str, ward: Optional[str] = None, plot_no: Optional[str] = None
    ) -> dict:
        """Analyze site: geocode, get nearby landmarks, query MCGM for zone."""
        geocode_result = await self._geocode(address, ward, plot_no)
        if not geocode_result:
            raise SiteAnalysisUnavailableError(
                "Geocoding failed — no API configured or all APIs errored"
            )

        lat = geocode_result["lat"]
        lng = geocode_result["lng"]

        # Query MCGM ArcGIS for real zone data
        zone_data = await self._query_mcgm_zone(lat, lng)

        return {
            "lat": lat,
            "lng": lng,
            "formatted_address": geocode_result["formatted_address"],
            "area_type": geocode_result["area_type"],
            "nearby_landmarks": geocode_result["nearby_landmarks"],
            "place_id": geocode_result["place_id"],
            "zone_inference": zone_data["zone"] if zone_data else None,
            "ward": zone_data["ward"] if zone_data else None,
            "zone_source": "mcgm_arcgis" if zone_data else "unavailable",
            "maps_url": geocode_result["maps_url"],
        }

    async def _geocode(
        self, address: str, ward: Optional[str], plot_no: Optional[str]
    ) -> Optional[dict]:
        """Geocode address via Google Maps API or SerpApi fallback."""
        query = address or f"Plot {plot_no}, {ward}, Mumbai, India"

        # 1. Try Official Google Maps API
        if self.gmaps:
            try:
                geocode_result = await asyncio.to_thread(self.gmaps.geocode, query)
                if geocode_result:
                    result = geocode_result[0]
                    lat = result["geometry"]["location"]["lat"]
                    lng = result["geometry"]["location"]["lng"]
                    formatted_address = result.get("formatted_address", query)
                    place_id = result.get("place_id", "")

                    nearby_result = await asyncio.to_thread(
                        functools.partial(
                            self.gmaps.places_nearby,
                            location=(lat, lng),
                            radius=500,
                            type="point_of_interest",
                        )
                    )

                    nearby_places = nearby_result.get("results", [])[:15]
                    landmarks = [
                        p.get("name")
                        for p in nearby_places
                        if p.get("name") and "unnamed" not in p.get("name").lower()
                    ][:6]

                    area_type = infer_area_type(nearby_places)
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={place_id}"

                    return {
                        "lat": lat,
                        "lng": lng,
                        "formatted_address": formatted_address,
                        "area_type": area_type,
                        "nearby_landmarks": landmarks,
                        "place_id": place_id,
                        "maps_url": maps_url,
                    }
            except Exception as e:
                logger.error(f"Google Maps API error: {e}")

        # 2. Fallback to SerpApi
        if settings.SERP_API_KEY:
            logger.info("Using SerpApi fallback for site analysis...")
            try:
                params = {
                    "engine": "google_maps",
                    "q": query,
                    "api_key": settings.SERP_API_KEY,
                    "type": "search",
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        "https://serpapi.com/search", params=params
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        place_results = data.get("place_results", {})
                        if not place_results and data.get("local_results"):
                            place_results = data["local_results"][0]

                        if place_results:
                            lat = place_results.get("gps_coordinates", {}).get("latitude")
                            lng = place_results.get("gps_coordinates", {}).get("longitude")
                            formatted_address = place_results.get("address", query)
                            local_results = data.get("local_results", [])
                            landmarks = [
                                r.get("title") for r in local_results if r.get("title")
                            ][:6]

                            area_type = "Mixed Use (Residential + Commercial)"
                            if any(
                                kw in str(place_results).lower()
                                for kw in ["shop", "mall", "office"]
                            ):
                                area_type = "Predominantly Commercial"

                            return {
                                "lat": lat,
                                "lng": lng,
                                "formatted_address": formatted_address,
                                "area_type": area_type,
                                "nearby_landmarks": landmarks,
                                "place_id": place_results.get("place_id", "serp_fallback"),
                                "maps_url": place_results.get("links", {}).get(
                                    "directions",
                                    f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
                                ),
                            }
            except Exception as e:
                logger.error(f"SerpApi fallback error: {e}")

        logger.error("Both Google Maps and SerpApi failed or are unconfigured")
        return None

    async def _query_mcgm_zone(
        self, lat: float, lng: float
    ) -> Optional[dict]:
        """
        Query MCGM ArcGIS for actual ward and zone at given coordinates.
        Returns {"ward": "G/S", "zone": "Residential (R)"} or None.
        """
        try:
            async with httpx.AsyncClient(timeout=20.0) as http:
                # Discover zone layer URL if not cached
                if not self._zone_layer_url:
                    self._zone_layer_url = await self._discover_zone_layer(http)
                if not self._zone_layer_url:
                    logger.warning("Could not discover MCGM zone layer")
                    return None

                # Point-in-polygon spatial query
                x, y = _wgs84_to_web_mercator(lng, lat)
                geometry = json.dumps(
                    {"x": x, "y": y, "spatialReference": {"wkid": 102100}}
                )
                params = {
                    "f": "json",
                    "geometry": geometry,
                    "geometryType": "esriGeometryPoint",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "*",
                    "returnGeometry": "false",
                }
                resp = await http.get(
                    f"{self._zone_layer_url}/query", params=params
                )
                resp.raise_for_status()
                features = resp.json().get("features", [])
                if features:
                    attrs = features[0].get("attributes", {})
                    up = {k.upper(): v for k, v in attrs.items()}
                    zone = _pick(up, _ZONE_FIELDS)
                    ward = _pick(up, _WARD_FIELDS)
                    if zone or ward:
                        logger.info("MCGM zone query: ward=%s, zone=%s", ward, zone)
                        return {"ward": ward, "zone": zone}

        except Exception as e:
            logger.warning("MCGM ArcGIS zone query failed: %s", e)

        return None

    async def _discover_zone_layer(self, http: httpx.AsyncClient) -> Optional[str]:
        """Search MCGM's ArcGIS portal for the DP 2034 zone feature layer."""
        search_url = f"{MCGM_PORTAL_URL}/sharing/rest/search"
        for query in [
            "DP 2034 zone owner:mcgm",
            "Development Plan 2034 owner:mcgm",
            "MCGM DP zone",
        ]:
            try:
                resp = await http.get(
                    search_url,
                    params={"q": query, "f": "json", "num": 10},
                    timeout=20.0,
                )
                resp.raise_for_status()
                items = resp.json().get("results", [])
                for item in items:
                    item_id = item.get("id", "")
                    if not item_id:
                        continue
                    url = await self._probe_item(item_id, http)
                    if url:
                        logger.info("Discovered MCGM zone layer: %s", url)
                        return url
            except Exception as e:
                logger.debug("Portal search '%s' failed: %s", query, e)

        return None

    async def _probe_item(
        self, item_id: str, http: httpx.AsyncClient
    ) -> Optional[str]:
        """Check if an ArcGIS portal item has a FeatureServer with zone fields."""
        try:
            resp = await http.get(
                f"{MCGM_PORTAL_URL}/sharing/rest/content/items/{item_id}",
                params={"f": "json"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            service_url = data.get("url", "")
            if not service_url or "FeatureServer" not in service_url:
                return None
            return await self._find_zone_layer(service_url, http)
        except Exception:
            return None

    async def _find_zone_layer(
        self, service_url: str, http: httpx.AsyncClient
    ) -> Optional[str]:
        """Walk FeatureServer layers to find the one with zone fields."""
        try:
            resp = await http.get(
                service_url, params={"f": "json"}, timeout=10.0
            )
            resp.raise_for_status()
            data = resp.json()
            for layer in data.get("layers", []):
                layer_url = f"{service_url}/{layer['id']}"
                try:
                    lr = await http.get(
                        layer_url, params={"f": "json"}, timeout=10.0
                    )
                    lr.raise_for_status()
                    fields = {f["name"].upper() for f in lr.json().get("fields", [])}
                    if fields & _ZONE_FIELDS:
                        return layer_url
                except Exception:
                    continue
        except Exception:
            pass
        return None


site_analysis_service = SiteAnalysisService()
```

- [ ] **Step 5: Update router to handle SiteAnalysisUnavailableError**

Replace `services/site_analysis/routers/site_router.py`:

```python
from fastapi import APIRouter, HTTPException
from schemas import SiteAnalysisRequest, SiteAnalysisResponse
from services.analyse import site_analysis_service, SiteAnalysisUnavailableError

router = APIRouter()


@router.post("/analyse", response_model=SiteAnalysisResponse)
async def analyse_site(req: SiteAnalysisRequest):
    """Analyze site location, landmarks, and MCGM zone data."""
    try:
        result = await site_analysis_service.analyse(
            address=req.address, ward=req.ward, plot_no=req.plot_no
        )
        return result
    except SiteAnalysisUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "geocoding_unavailable",
                "message": str(e),
                "suggestion": "Check API keys or provide coordinates manually",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health():
    return {"status": "ok", "service": "site_analysis"}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd C:/Users/Admin/Documents/Projects/redevelopment-ai && python -m pytest tests/test_site_analysis.py -v`
Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add services/site_analysis/services/analyse.py services/site_analysis/schemas/__init__.py services/site_analysis/routers/site_router.py tests/test_site_analysis.py
git commit -m "feat(site-analysis): replace heuristic zone with MCGM ArcGIS query, remove mock"
```

---

## Task 4: Run All Tests and Final Commit

**Files:** None new — verification only.

- [ ] **Step 1: Run full test suite**

Run: `cd C:/Users/Admin/Documents/Projects/redevelopment-ai && python -m pytest tests/test_pr_card_extractor.py tests/test_height_service.py tests/test_site_analysis.py -v`
Expected: All 15 tests PASS

- [ ] **Step 2: Verify no import errors in each service**

Run these in sequence:
```bash
cd C:/Users/Admin/Documents/Projects/redevelopment-ai/services/pr_card_scraper && python -c "from services.data_extractor import LLMDataExtractor; print('PR Card OK')"
cd C:/Users/Admin/Documents/Projects/redevelopment-ai/services/height_service && python -c "from services.height_service import HeightService, NOCASUnavailableError; print('Height OK')"
cd C:/Users/Admin/Documents/Projects/redevelopment-ai/services/site_analysis && python -c "from services.analyse import SiteAnalysisService, SiteAnalysisUnavailableError; print('Site OK')"
```

Expected: All print OK with no import errors.

- [ ] **Step 3: Final commit if any fixups needed**

```bash
git add -A
git commit -m "fix: resolve any import or test issues from three-service improvements"
```
