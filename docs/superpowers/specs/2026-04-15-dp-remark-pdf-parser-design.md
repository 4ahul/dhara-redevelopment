# DP Remark PDF Parser — Design Spec

**Date:** 2026-04-15
**Service:** `services/dp_report_service`
**Goal:** Build a text-based PDF parser for DP Remark reports (SRDP 1991 and DP 2034 formats) and extend the schema to capture all extractable fields.

---

## Problem Statement

The `dp_report_service` automates fetching Development Plan remarks from MCGM portals. The DPRMarks portal (`dpremarks.mcgm.gov.in`) produces a PDF report as its final output after login, form submission, and payment. Currently the service only scrapes web page text and ArcGIS JSON — it cannot parse the actual PDF output.

Reference PDFs available:
- `test_docs/DP Remark 1991 .pdf` — SRDP (Sanctioned Revised Development Plan), CTS-based, 2 pages
- `test_docs/DP Remark 2034 FP 18.pdf` — DP 2034, FP-based, 4 pages (simple case)
- `services/dp_report_service/sample/Remark_ReportDP34202505111599881.pdf` — Government sample DP 2034, CTS-based, 9 pages (complex case with all possible fields)

The user provides either CTS number or FP number as input. The portal returns the corresponding report format. **Note:** DP 2034 reports can be both CTS-based and FP-based.

## PDF Characteristics

### SRDP 1991 Format (CTS-based)
- 2 pages: text report + block/location plan
- Header: "SRDP 1991" and "MUNICIPAL CORPORATION OF GREATER MUMBAI"
- Reference: `CHE: SRDP{date}{id}`
- Identifies land by **CTS numbers** and village
- Fields: zone, reservations (affecting/abutting), designations (affecting/abutting), DP roads, RL remarks (traffic)
- Label-value format: `"Description of the land: ..."`, `"Zones [as shown on plan]: ..."`

### DP 2034 Format (CTS or FP-based)
- 4-9 pages depending on complexity
- Header: "DP 2034 Remarks"
- Reference: `Ch.E./DP34{date}{id}`
- Identifies land by **CTS number** OR **FP number** (and optionally TPS scheme)
- All 1991 fields PLUS:
  - Heritage status (5 yes/no questions)
  - Existing amenities (affecting/abutting)
  - Water pipeline (diameter, distance)
  - Sewer line (manhole node, invert level, distance)
  - Drainage (node ID, distance, invert level) — from govt sample
  - Ground level (min/max with THD datum)
  - RL remarks from both Traffic and Survey depts
  - Proposed road and widening status
  - EP/SM sheet numbers with notification details — from govt sample
  - CRZ zone details with categories — from govt sample
  - SGNP buffer / mangrove remarks — from govt sample
  - Flamingo ESZ remarks — from govt sample
  - High voltage line remarks — from govt sample
  - DCPR corrections, Sec 37 modifications, road realignment — from govt sample
  - Multiple zones per plot (e.g., "NA,R,NDZ,I,SDZ") — from govt sample
  - Affected area per zone in sqm — from govt sample
- Table-style layout: Description | Nomenclature | Remarks columns

## Design

### 1. Extended DPReportResponse Schema

**File:** `services/dp_report_service/schemas/__init__.py`

Existing fields are preserved. New fields added:

| Field | Type | Source | Example |
|-------|------|--------|---------|
| `report_type` | Optional[str] | Both | `"SRDP_1991"` or `"DP_2034"` |
| `reference_no` | Optional[str] | Both | `"SRDP202211111425043"` |
| `report_date` | Optional[str] | Both | `"04/11/2022"` |
| `applicant_name` | Optional[str] | Both | `"Jinish N Soni"` |
| `cts_nos` | Optional[list[str]] | 1991 | `["852","853","855","854"]` |
| `fp_no` | Optional[str] | 2034 | `"18"` |
| `tps_name` | Optional[str] | 2034 | `"TPS VILE PARLE No.VI"` |
| `reservations_affecting` | Optional[str] | Both | `"NO"` |
| `reservations_abutting` | Optional[str] | Both | `"NO"` |
| `designations_affecting` | Optional[str] | 1991 | `"NO"` |
| `designations_abutting` | Optional[str] | 1991 | `"NO"` |
| `dp_roads` | Optional[str] | Both | `"EXISTING ROAD"` |
| `proposed_road` | Optional[str] | 2034 | `"NIL"` |
| `proposed_road_widening` | Optional[str] | 2034 | `"NIL"` |
| `rl_remarks_traffic` | Optional[str] | Both | Full traffic dept remark |
| `rl_remarks_survey` | Optional[str] | 2034 | Full survey dept remark |
| `water_pipeline` | Optional[dict] | 2034 | `{"diameter_mm": 250, "distance_m": 3.44}` |
| `sewer_line` | Optional[dict] | 2034 | `{"node_no": "15240911", "distance_m": 6.82, "invert_level_m": 28.50}` |
| `ground_level` | Optional[dict] | 2034 | `{"min_m": 32.40, "max_m": 33.00, "datum": "THD"}` |
| `heritage_building` | Optional[str] | 2034 | `"Yes"` / `"No"` |
| `heritage_precinct` | Optional[str] | 2034 | `"Yes"` / `"No"` |
| `heritage_buffer_zone` | Optional[str] | 2034 | `"Yes"` / `"No"` |
| `archaeological_site` | Optional[str] | 2034 | `"Yes"` / `"No"` |
| `archaeological_buffer` | Optional[str] | 2034 | `"Yes"` / `"No"` |
| `existing_amenities_affecting` | Optional[str] | 2034 | `"NO"` |
| `existing_amenities_abutting` | Optional[str] | 2034 | `"NO"` |
| `crz_zone_details` | Optional[dict] | 2034 | `{"categories": ["CRZ I", "CRZ IV"], "text": "..."}` |
| `drainage` | Optional[dict] | 2034 | `{"node_id": "2181081004", "distance_m": 0.0, "invert_level_m": 26.30}` |
| `high_voltage_line` | Optional[str] | 2034 | Full text about HT power lines |
| `buffer_sgnp` | Optional[str] | 2034 | SGNP/mangrove buffer text |
| `flamingo_esz` | Optional[str] | 2034 | Flamingo ESZ text |
| `corrections_dcpr` | Optional[str] | 2034 | DCPR 2034 corrections text |
| `modifications_sec37` | Optional[str] | 2034 | Section 37 modifications text |
| `road_realignment` | Optional[str] | 2034 | Road realignment text |
| `ep_nos` | Optional[list[str]] | 2034 | `["EP-ME81", "EP-ME75"]` |
| `sm_nos` | Optional[list[str]] | 2034 | `["SM-ME21"]` |
| `pdf_text` | Optional[str] | Both | Full extracted text |

All fields are Optional since different DP remark reports may have different fields present.

### 2. PDF Parser Module

**New file:** `services/dp_report_service/services/dp_pdf_parser.py`

**Public API:**
```python
def parse_dp_pdf(pdf_bytes: bytes) -> dict:
    """Parse a DP Remark PDF into a structured dict matching DPReportResponse fields."""
```

**Internal flow:**
1. Extract text from all pages using `pypdf.PdfReader`
2. Detect format: check for `"SRDP"` in text → 1991, check for `"DP 2034"` → 2034
3. Dispatch to format-specific parser:
   - `_parse_srdp_1991(full_text: str) -> dict`
   - `_parse_dp_2034(full_text: str) -> dict`
4. Both parsers return a dict with matching keys to `DPReportResponse`
5. Fields not available in a format are set to `None`

**Parsing strategies per field type:**

- **Label-value pairs** (zone, reservations, etc.): Regex matching the label text, capture value after colon/whitespace. Example: `r"Zones?\s*\[.*?\]\s*[:.]?\s*(.+)"`
- **Table rows (2034):** Match left-column description text, capture right-column value. Example: `r"Zone\s*\[as shown on plan\]\s*(.+)"`
- **Infrastructure data (2034):** Pattern-match numeric values. Examples:
  - Water: `r"(\d+)\s*mm\s*pipe.*?(\d+\.?\d*)\s*meters?\s*far"`
  - Sewer: `r"Node No\.\s*(\d+).*?(\d+\.?\d*)\s*meters?\s*far.*?invert level\s*(\d+\.?\d*)"`
  - Ground: `r"minimum\s*(\d+\.?\d*).*?maximum\s*(\d+\.?\d*).*?meters?\s*ground level"`
- **Heritage yes/no block (2034):** Match each question's unique text and capture the trailing Yes/No
- **Multi-line fields** (RL remarks): Capture text between the section header and the next section boundary (e.g., next "Remark:" header or "Note:" or "Acc:")
- **Reference number:** `r"CHE\s*[:.]\s*(\S+)"` for 1991, `r"Ch\.?E\.?/(\S+)"` for 2034
- **CTS numbers:** `r"C\.?T\.?S\.?\s*No\.?\(?s?\)?\s*([\d,\s/\-]+)\s+of\s+(\w[\w\s]+?)(?:\s+Village|\s*$)"`
- **FP number:** `r"F\.?P\.?\s*No\.?\(?s?\)?\s*(\d+)"`

### 3. Database Schema Update

**File:** `services/dp_report_service/services/storage.py`

Add new columns to the `dp_reports` table:

```
report_type          VARCHAR(20)
reference_no         VARCHAR(100)
report_date          VARCHAR(20)
applicant_name       VARCHAR(200)
cts_nos              JSONB          -- list of CTS numbers
fp_no                VARCHAR(50)
tps_name             VARCHAR(200)
reservations_affecting VARCHAR(500)
reservations_abutting  VARCHAR(500)
designations_affecting VARCHAR(500)
designations_abutting  VARCHAR(500)
dp_roads             VARCHAR(500)
proposed_road        VARCHAR(200)
proposed_road_widening VARCHAR(200)
rl_remarks_traffic   TEXT
rl_remarks_survey    TEXT
water_pipeline       JSONB
sewer_line           JSONB
ground_level         JSONB
heritage_building    VARCHAR(10)
heritage_precinct    VARCHAR(10)
heritage_buffer_zone VARCHAR(10)
archaeological_site  VARCHAR(10)
archaeological_buffer VARCHAR(10)
existing_amenities_affecting VARCHAR(500)
existing_amenities_abutting  VARCHAR(500)
pdf_text             TEXT
pdf_bytes            BYTEA          -- raw PDF for re-parsing
```

### 4. New API Endpoint

**File:** `services/dp_report_service/routers/__init__.py`

```
POST /parse-pdf
  Body: raw PDF bytes (multipart file upload)
  Returns: DPReportResponse with all parsed fields
```

This endpoint allows:
- Independent testing of the parser without browser automation
- Manual upload of DP Remark PDFs
- Future use by other services that obtain PDFs through different channels

### 5. Integration Point in Scraper

**File:** `services/dp_report_service/services/dp_scraper.py`

Minimal change — import the parser and add a comment/hook in `_try_dprmarks_portal` indicating where the PDF download + parse will be called once payment automation is added. The existing flow continues working as-is.

When browser automation can download PDFs:
```python
# In _try_dprmarks_portal, after challan creation:
pdf_bytes = await self._download_report_pdf(page)
if pdf_bytes:
    from .dp_pdf_parser import parse_dp_pdf
    parsed = parse_dp_pdf(pdf_bytes)
    return {"attributes": parsed, "pdf_bytes": pdf_bytes, ...}
```

## Files Changed

| File | Change |
|------|--------|
| `dp_report_service/schemas/__init__.py` | Extend `DPReportResponse` with ~25 new fields |
| `dp_report_service/services/dp_pdf_parser.py` | **New file** — format detection, 1991 parser, 2034 parser |
| `dp_report_service/services/storage.py` | Add new columns to `dp_reports` table |
| `dp_report_service/routers/__init__.py` | Add `POST /parse-pdf` endpoint |
| `dp_report_service/services/dp_scraper.py` | Import parser, add integration hook comment |
| `dp_report_service/setup.py` | Add `pypdf` dependency |

## What Does NOT Change

- `dp_arcgis_client.py` — ArcGIS REST queries untouched
- `dp_scraper.py` browser automation flow — payment integration comes later
- Orchestrator / `shared/models.py` — later phase
- Other services (rag_service, pr_card_scraper)

## Testing Strategy

- Parse `test_docs/DP Remark 1991 .pdf` — assert all 1991 fields extract correctly
- Parse `test_docs/DP Remark 2034 FP 18.pdf` — assert all 2034 fields including infrastructure data (simple case)
- Parse `services/dp_report_service/sample/Remark_ReportDP34202505111599881.pdf` — assert complex fields: CRZ details, drainage, high voltage, SGNP buffer, flamingo ESZ, EP/SM numbers, multiple zones, DCPR corrections
- Test format auto-detection on all three PDFs
- Test graceful handling: 1991 PDF should return `None` for 2034-only fields
- Test that DP 2034 with CTS numbers (govt sample) correctly extracts cts_nos
- Test `/parse-pdf` endpoint with all three test PDFs
- Test with a non-DP PDF to verify graceful error handling
