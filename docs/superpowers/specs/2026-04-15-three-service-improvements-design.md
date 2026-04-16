# Three-Service Improvement Design — PR Card OCR, Height Service, Site Analysis

**Date:** 2026-04-15
**Services:** `pr_card_scraper`, `height_service`, `site_analysis`
**Goal:** Extract structured data from PR card images, remove mock/fake data from height service, replace heuristic zone inference with real MCGM data in site analysis.

---

## 1. PR Card Scraper — LLM Vision OCR

### Problem

`DataExtractor.extract()` returns `{}` always. The PR card image is captured successfully but no structured data is extracted. The feasibility report needs plot area, CTS number, and other fields from this image.

### PR Card Image Structure

The Mahabhumi Property Card has these fields:

| Field | Needed for Report |
|-------|-------------------|
| Property UID | Reference |
| Village/Patti, Taluka, District | Cross-validation |
| CTS No | Annexure II (FSI) |
| Sheet Number | Reference |
| Plot Number | Annexure II (FSI) |
| Area Sq.Mt. | Annexure II — plot area from PR card |
| Tenure | Legal reference |
| Assessment | Reference |
| Enumeration Year | Reference |
| Name of Holder | Cover page, legal |
| Other Encumbrances/Rights | Legal notes |
| Transactions (Date, Vol, Holder) | Legal history |

### Design

**File:** `services/pr_card_scraper/services/data_extractor.py`

Replace the stub with `LLMDataExtractor` using Gemini Flash -> GPT-4o (same pattern as `llm_captcha_solver.py`).

**Extraction prompt:** Structured JSON output requesting all PR card fields. Image preparation: 2x upscale + contrast boost (same as captcha solver).

**Key details:**
- Gemini model: `gemini-2.0-flash`, `temperature: 0`, `maxOutputTokens: 1024`
- JSON parsing with fallback regex for partial responses
- Validation: `area_sqm` is numeric and reasonable (0.1 - 100000), `cts_no` is non-empty
- `extract()` becomes `async` — update caller in `browser/__init__.py`
- Added metadata: `extraction_confidence` (high/medium/low) and `extraction_source` (which LLM)

---

## 2. Height Service — Remove Mock, Fail Honestly

### Problem

On NOCAS failure, service silently returns mock data (70m, 23 floors). Report generator cannot distinguish real vs fake.

### Design

**File:** `services/height_service/services/height_service.py`

- Add **3 attempts** (1 initial + 2 retries) with fresh browser context
- Extract scraping logic into `_fetch_from_nocas()` private method
- **Delete `_mock_response()` entirely**
- On all retries exhausted: raise `NOCASUnavailableError` -> HTTP 503
- New schema fields: `is_real_data: bool`, `data_source: str`, `attempt: int`

---

## 3. Site Analysis — Replace Heuristic Zone with MCGM ArcGIS

### Problem

`infer_zone()` is a hardcoded map of ~10 Mumbai localities. Wrong for most areas.

### Design

**File:** `services/site_analysis/services/analyse.py`

- After geocoding gives lat/lng, query MCGM ArcGIS FeatureServer with a point-in-polygon spatial query
- **Delete `infer_zone()` function entirely**
- **Delete `_mock_response()` method entirely**
- On geocoding failure: raise `SiteAnalysisUnavailableError` -> HTTP 503
- New schema fields: `ward: Optional[str]`, `zone_source: str`
- `zone_inference` becomes nullable (None when ArcGIS unavailable)
- Keep `area_type` inference from Google Places (reasonable heuristic)

---

## Files Changed

| Service | File | Change |
|---------|------|--------|
| pr_card_scraper | `services/data_extractor.py` | Replace stub with `LLMDataExtractor` |
| pr_card_scraper | `services/browser/__init__.py` | Make `extract()` call async |
| height_service | `services/height_service.py` | Add retry, remove mock, add exception |
| height_service | `schemas/__init__.py` | Add `is_real_data`, `data_source`, `attempt` |
| height_service | `routers/__init__.py` | Handle `NOCASUnavailableError` -> 503 |
| site_analysis | `services/analyse.py` | Add MCGM ArcGIS query, remove infer_zone, remove mock |
| site_analysis | `schemas/__init__.py` | Add `ward`, `zone_source`, make `zone_inference` nullable |
| site_analysis | `routers/__init__.py` | Handle `SiteAnalysisUnavailableError` -> 503 |

---

## Testing

1. **PR Card OCR** — Run scraper against known property, verify `extracted_data` has correct `cts_no`, `area_sqm`, `holders`
2. **Height Service** — Test with real coords (18.9967, 72.8325). Verify real data returns. Verify 503 on failure (not mock).
3. **Site Analysis** — Test with "Prabhadevi, Mumbai". Verify `zone_source: "mcgm_arcgis"` and `ward` populated. Verify 503 on geocoding failure.
