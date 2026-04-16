# DP Remark PDF Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a text-based PDF parser for DP Remark reports (SRDP 1991 and DP 2034 formats), extend the `DPReportResponse` schema, update the database, and add a `/parse-pdf` endpoint.

**Architecture:** New `dp_pdf_parser.py` module extracts text via `pypdf`, auto-detects format (1991 vs 2034), dispatches to format-specific regex parsers, returns a dict matching the extended `DPReportResponse` schema. Database and API get new fields to store the richer data.

**Tech Stack:** Python, pypdf, regex, FastAPI, PostgreSQL (psycopg2), Pydantic

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `services/dp_report_service/services/dp_pdf_parser.py` | Create | PDF text extraction, format detection, field parsing for 1991 + 2034 |
| `services/dp_report_service/schemas/__init__.py` | Modify | Extend `DPReportResponse` with ~25 new fields |
| `services/dp_report_service/services/storage.py` | Modify | Add new columns, update `update_report` and `get_report` |
| `services/dp_report_service/routers/__init__.py` | Modify | Add `POST /parse-pdf` endpoint, update existing endpoints to populate new fields |
| `services/dp_report_service/pyproject.toml` | Modify | Add `pypdf` dependency |
| `services/dp_report_service/tests/__init__.py` | Create | Test package |
| `services/dp_report_service/tests/test_dp_pdf_parser.py` | Create | Unit tests for PDF parser (all 3 test PDFs) |

---

### Task 1: Add pypdf Dependency

**Files:**
- Modify: `services/dp_report_service/pyproject.toml:6-15`

- [ ] **Step 1: Add pypdf to dependencies**

In `services/dp_report_service/pyproject.toml`, add `"pypdf>=4.0.0"` to the dependencies list:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "playwright>=1.40.0",
    "playwright-stealth>=1.0.6",
    "httpx>=0.27.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.7.0",
    "psycopg2-binary>=2.9.0",
    "pypdf>=4.0.0",
]
```

- [ ] **Step 2: Install the dependency**

Run: `cd services/dp_report_service && pip install pypdf>=4.0.0`
Expected: Successfully installed pypdf

- [ ] **Step 3: Verify import works**

Run: `python -c "from pypdf import PdfReader; print('pypdf OK')"`
Expected: `pypdf OK`

- [ ] **Step 4: Commit**

```bash
git add services/dp_report_service/pyproject.toml
git commit -m "chore: add pypdf dependency for DP Remark PDF parsing"
```

---

### Task 2: Build the DP 2034 PDF Parser

**Files:**
- Create: `services/dp_report_service/tests/__init__.py`
- Create: `services/dp_report_service/tests/test_dp_pdf_parser.py`
- Create: `services/dp_report_service/services/dp_pdf_parser.py`

- [ ] **Step 1: Create test directory and write failing tests**

Create empty `services/dp_report_service/tests/__init__.py`.

Create `services/dp_report_service/tests/test_dp_pdf_parser.py`:

```python
"""Tests for DP Remark PDF parser — DP 2034 format."""

import os
import pytest

# Test PDF path
TEST_DOCS = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "test_docs"
)
DP_2034_PDF = os.path.join(TEST_DOCS, "DP Remark 2034 FP 18.pdf")


@pytest.fixture(scope="module")
def dp_2034_result():
    from services.dp_pdf_parser import parse_dp_pdf
    with open(DP_2034_PDF, "rb") as f:
        return parse_dp_pdf(f.read())


@pytest.mark.skipif(
    not os.path.exists(DP_2034_PDF),
    reason="Test PDF not found",
)
class TestDP2034Parser:
    def test_format_detection(self, dp_2034_result):
        assert dp_2034_result["report_type"] == "DP_2034"

    def test_reference_no(self, dp_2034_result):
        assert "DP34202211111425031" in dp_2034_result["reference_no"]

    def test_report_date(self, dp_2034_result):
        assert dp_2034_result["report_date"] == "04/11/2022"

    def test_applicant_name(self, dp_2034_result):
        assert "Jinish" in dp_2034_result["applicant_name"]

    def test_fp_no(self, dp_2034_result):
        assert dp_2034_result["fp_no"] == "18"

    def test_tps_name(self, dp_2034_result):
        assert "VILE PARLE" in dp_2034_result["tps_name"]

    def test_ward(self, dp_2034_result):
        assert dp_2034_result["ward"] == "K/W"

    def test_village(self, dp_2034_result):
        assert "VILE PARLE" in dp_2034_result["village"]

    def test_zone(self, dp_2034_result):
        zone = dp_2034_result["zone_name"]
        assert zone is not None
        assert "Residential" in zone or "R" in zone

    def test_existing_road(self, dp_2034_result):
        assert dp_2034_result["dp_roads"] is not None
        assert "Present" in dp_2034_result["dp_roads"] or "EXISTING" in dp_2034_result["dp_roads"]

    def test_proposed_road(self, dp_2034_result):
        assert dp_2034_result["proposed_road"] == "NIL"

    def test_proposed_road_widening(self, dp_2034_result):
        assert dp_2034_result["proposed_road_widening"] == "NIL"

    def test_reservations(self, dp_2034_result):
        assert dp_2034_result["reservations_affecting"] == "NO"
        assert dp_2034_result["reservations_abutting"] == "NO"

    def test_existing_amenities(self, dp_2034_result):
        assert dp_2034_result["existing_amenities_affecting"] == "NO"
        assert dp_2034_result["existing_amenities_abutting"] == "NO"

    def test_water_pipeline(self, dp_2034_result):
        wp = dp_2034_result["water_pipeline"]
        assert wp is not None
        assert wp["diameter_mm"] == 250
        assert wp["distance_m"] == pytest.approx(3.44, abs=0.01)

    def test_sewer_line(self, dp_2034_result):
        sl = dp_2034_result["sewer_line"]
        assert sl is not None
        assert sl["node_no"] == "15240911"
        assert sl["distance_m"] == pytest.approx(6.82, abs=0.01)
        assert sl["invert_level_m"] == pytest.approx(28.50, abs=0.01)

    def test_ground_level(self, dp_2034_result):
        gl = dp_2034_result["ground_level"]
        assert gl is not None
        assert gl["min_m"] == pytest.approx(32.40, abs=0.01)
        assert gl["max_m"] == pytest.approx(33.00, abs=0.01)
        assert gl["datum"] == "THD"

    def test_rl_remarks_traffic(self, dp_2034_result):
        rl = dp_2034_result["rl_remarks_traffic"]
        assert rl is not None
        assert "Traffic" in rl or "traffic" in rl

    def test_rl_remarks_survey(self, dp_2034_result):
        rl = dp_2034_result["rl_remarks_survey"]
        assert rl is not None
        assert "Survey" in rl or "survey" in rl

    def test_pdf_text_present(self, dp_2034_result):
        assert dp_2034_result["pdf_text"] is not None
        assert len(dp_2034_result["pdf_text"]) > 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/dp_report_service && python -m pytest tests/test_dp_pdf_parser.py -v`
Expected: FAIL — `dp_pdf_parser` module doesn't exist yet.

- [ ] **Step 3: Implement the parser**

Create `services/dp_report_service/services/dp_pdf_parser.py`:

```python
"""
DP Remark PDF Parser
Extracts structured data from MCGM Development Plan remark PDFs.
Supports: SRDP 1991 (CTS-based) and DP 2034 (FP-based) formats.
"""

import io
import logging
import re
from typing import Optional

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def parse_dp_pdf(pdf_bytes: bytes) -> dict:
    """
    Parse a DP Remark PDF into a structured dict.
    Auto-detects format (SRDP 1991 vs DP 2034).
    Returns dict with keys matching DPReportResponse fields.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        logger.error("Failed to read PDF: %s", e)
        return {"error": f"Invalid PDF: {e}"}

    full_text = "\n".join(
        page.extract_text() or "" for page in reader.pages
    )

    if not full_text.strip():
        return {"error": "PDF contains no extractable text (scanned image?)"}

    # Detect format
    if "SRDP" in full_text[:200]:
        report_type = "SRDP_1991"
        result = _parse_srdp_1991(full_text)
    elif "DP 2034" in full_text[:200] or "DP2034" in full_text[:500]:
        report_type = "DP_2034"
        result = _parse_dp_2034(full_text)
    else:
        report_type = "UNKNOWN"
        # Try 2034 parser as default (it's the primary expected format)
        result = _parse_dp_2034(full_text)

    result["report_type"] = report_type
    result["pdf_text"] = full_text
    return result


# ── DP 2034 Parser ───────────────────────────────────────────────────────────


def _parse_dp_2034(text: str) -> dict:
    """Parse DP 2034 format PDF text."""
    result = {}

    # Reference number: Ch.E./DP34202211111425031
    m = re.search(r"Ch\.?E\.?[/.](\S+)", text)
    result["reference_no"] = m.group(1) if m else None

    # Report date — from "Payment Dated DD/MM/YYYY" or "Dated: DD/MM/YYYY"
    m = re.search(r"Dated[:\s]+(\d{2}/\d{2}/\d{4})", text)
    result["report_date"] = m.group(1) if m else None

    # Applicant name — "Mr./Mrs. Name"
    m = re.search(r"Mr\.?/Mrs\.?\s+(.+?)$", text, re.MULTILINE)
    result["applicant_name"] = m.group(1).strip() if m else None

    # FP number — "F.P. No(s) 18"
    m = re.search(r"F\.?P\.?\s*No\.?\(?s?\)?\s*(\d+)", text)
    result["fp_no"] = m.group(1) if m else None

    # TPS name — "TPS VILE PARLE No.VI"
    m = re.search(r"(?:of\s+)?TPS\s+(.+?)(?:\s+situated|\s+in\s+\w+/\w+\s+Ward)", text)
    if m:
        result["tps_name"] = m.group(1).strip()
    else:
        m = re.search(r"^TPS\s+(.+)$", text, re.MULTILINE)
        result["tps_name"] = m.group(1).strip() if m else None

    # Ward — "K/W Ward" or "referred to Ward K/W"
    m = re.search(r"(?:referred to|in)\s+(?:Ward\s+)?(\w+/\w+)\s+Ward", text)
    if not m:
        m = re.search(r"Ward\s+(\w+/\w+)", text)
    result["ward"] = m.group(1) if m else None

    # Village — from subject line or TPS reference
    m = re.search(r"of\s+(?:TPS\s+)?(\w[\w\s]+?)(?:\s+(?:Village|situated|in\s+\w+/\w+))", text)
    result["village"] = m.group(1).strip() if m else None

    # Zone — "Zone [as shown on plan] Residential(R)"
    m = re.search(r"Zone\s*\[as shown on plan\]\s*(.+?)$", text, re.MULTILINE)
    result["zone_name"] = m.group(1).strip() if m else None

    # Extract zone_code from zone_name like "Residential(R)" -> "R"
    if result.get("zone_name"):
        zm = re.search(r"\((\w+)\)", result["zone_name"])
        result["zone_code"] = zm.group(1) if zm else None
    else:
        result["zone_code"] = None

    # Roads
    m = re.search(r"Existing Road\s+(.+?)$", text, re.MULTILINE)
    result["dp_roads"] = f"Existing Road {m.group(1).strip()}" if m else None

    m = re.search(r"Proposed Road\s+(?!Widening)(.+?)$", text, re.MULTILINE)
    result["proposed_road"] = m.group(1).strip() if m else None

    m = re.search(r"Proposed Road Widening\s+(.+?)$", text, re.MULTILINE)
    result["proposed_road_widening"] = m.group(1).strip() if m else None

    # Reservations
    m = re.search(r"Reservation affecting.*?\]\s*(.+?)$", text, re.MULTILINE)
    result["reservations_affecting"] = m.group(1).strip() if m else None

    m = re.search(r"Reservation abutting.*?\]\s*(.+?)$", text, re.MULTILINE)
    result["reservations_abutting"] = m.group(1).strip() if m else None

    # Existing amenities
    m = re.search(r"Existing amenities affecting.*?\]\s*(.+?)$", text, re.MULTILINE)
    result["existing_amenities_affecting"] = m.group(1).strip() if m else None

    m = re.search(r"Existing amenities abutting.*?\]\s*(.+?)$", text, re.MULTILINE)
    result["existing_amenities_abutting"] = m.group(1).strip() if m else None

    # Designations (not in 2034 format typically, set None)
    result["designations_affecting"] = None
    result["designations_abutting"] = None

    # Heritage questions — these appear as "Whether ... Yes / No"
    # The PDF renders them oddly: "Yes / NoWhether situated in a Heritage Precinct:"
    _parse_heritage_2034(text, result)

    # Infrastructure: Water pipeline
    m = re.search(
        r"Water pipeline.*?\((\d+\.?\d*)\s*meters?\s*far\)\s*has\s*(\d+)\s*mm",
        text, re.IGNORECASE
    )
    if m:
        result["water_pipeline"] = {
            "distance_m": float(m.group(1)),
            "diameter_mm": int(m.group(2)),
        }
    else:
        result["water_pipeline"] = None

    # Infrastructure: Sewer line
    m = re.search(
        r"(?:Sewer|Sewerline).*?Node\s*No\.?\s*(\d+).*?(\d+\.?\d*)\s*meters?\s*far.*?"
        r"invert level\s*(\d+\.?\d*)",
        text, re.IGNORECASE | re.DOTALL
    )
    if m:
        result["sewer_line"] = {
            "node_no": m.group(1),
            "distance_m": float(m.group(2)),
            "invert_level_m": float(m.group(3)),
        }
    else:
        result["sewer_line"] = None

    # Infrastructure: Ground level
    m = re.search(
        r"minimum\s+(\d+\.?\d*)\s*meters?\s*and\s*maximum\s+(\d+\.?\d*)\s*meters?\s*ground level",
        text, re.IGNORECASE
    )
    if m:
        result["ground_level"] = {
            "min_m": float(m.group(1)),
            "max_m": float(m.group(2)),
            "datum": "THD",
        }
    else:
        result["ground_level"] = None

    # RL Remarks — Traffic
    result["rl_remarks_traffic"] = _extract_section(
        text,
        r"REGULAR LINE REMARKS \(Traffic\):",
        r"(?:REGULAR LINE REMARKS \(Survey\)|Acc:|Note:|This is electronically)",
    )

    # RL Remarks — Survey
    result["rl_remarks_survey"] = _extract_section(
        text,
        r"REGULAR LINE REMARKS \(Survey\):",
        r"(?:Acc:|Note:|This is electronically)",
    )

    # CTS numbers (not primary in 2034, but might appear in text)
    result["cts_nos"] = None

    # Populate legacy fields for compatibility
    result["dp_remarks"] = result.get("pdf_text", "")[:2000] if result.get("pdf_text") else None
    road_width = _extract_road_width(text)
    result["road_width_m"] = road_width
    result["fsi"] = None  # Not in DP remark PDF
    result["height_limit_m"] = None  # Not in DP remark PDF
    result["reservations"] = _build_reservations_list(result)
    result["crz_zone"] = None
    result["heritage_zone"] = _any_heritage_yes(result)

    return result


def _parse_heritage_2034(text: str, result: dict):
    """Parse the heritage yes/no block in DP 2034 format.

    The PDF text renders these oddly due to column layout:
      'Whether a listed Heritage building/ site: Yes / No'
      'Yes / NoWhether situated in a Heritage Precinct:'
    We look for each question and try to determine the answer.
    """
    # Heritage building
    m = re.search(r"Heritage building.*?:\s*(Yes|No)", text, re.IGNORECASE)
    result["heritage_building"] = m.group(1) if m else None

    # Heritage precinct
    m = re.search(r"Heritage Precinct.*?:\s*(Yes|No)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"(Yes|No)\s*/\s*(?:No|Yes)\s*Whether situated in a Heritage Precinct", text)
    result["heritage_precinct"] = m.group(1) if m else None

    # Heritage buffer zone
    m = re.search(r"buffer zone.*?heritage site.*?:\s*(Yes|No)", text, re.IGNORECASE | re.DOTALL)
    if not m:
        m = re.search(r"(Yes|No)\s*/\s*(?:No|Yes)\s*Whether situated in the buffer zone.*?heritage", text)
    result["heritage_buffer_zone"] = m.group(1) if m else None

    # Archaeological site (ASI)
    m = re.search(r"archaeological site.*?ASI.*?:\s*(Yes|No)", text, re.IGNORECASE)
    result["archaeological_site"] = m.group(1) if m else None

    # Archaeological buffer
    m = re.search(r"buffer zone.*?archaeological.*?ASI.*?:\s*(Yes|No)", text, re.IGNORECASE | re.DOTALL)
    if not m:
        m = re.search(r"(Yes|No)\s*/\s*(?:No|Yes)\s*Whether situated in the buffer zone.*?archaeological", text)
    result["archaeological_buffer"] = m.group(1) if m else None


# ── SRDP 1991 Parser ─────────────────────────────────────────────────────────


def _parse_srdp_1991(text: str) -> dict:
    """Parse SRDP 1991 format PDF text."""
    result = {}

    # Reference number: SRDP202211111425043
    m = re.search(r"No\s+CHE\.?\s*:\s*(\S+)", text)
    result["reference_no"] = m.group(1) if m else None

    # Report date
    m = re.search(r"Report Date\s*:\s*(\d{2}/\d{2}/\d{4})", text)
    result["report_date"] = m.group(1) if m else None

    # Applicant name — "Mr./Mrs. : Name"
    m = re.search(r"Mr\.?/Mrs\.?\s*:?\s*(.+?)$", text, re.MULTILINE)
    result["applicant_name"] = m.group(1).strip() if m else None

    # CTS numbers — "C.T.S. No(s) 852,853,855 and 854 of VILE PARLE"
    m = re.search(
        r"C\.?T\.?S\.?\s*No\.?\(?s?\)?\s*([\d,\s]+(?:\s*and\s*\d+)?)\s+of\s+(\w[\w\s]*?)(?:\s*Village|\s*$)",
        text, re.MULTILINE
    )
    if m:
        raw_nums = m.group(1)
        # Parse "852,853,855 and 854" into list
        nums = re.split(r"[,\s]+and\s+|[,\s]+", raw_nums)
        result["cts_nos"] = [n.strip() for n in nums if n.strip()]
        result["village"] = m.group(2).strip()
    else:
        result["cts_nos"] = None
        result["village"] = None

    # Ward — "referred to ward: K/W"
    m = re.search(r"referred to ward:\s*(\S+)", text)
    result["ward"] = m.group(1) if m else None

    # Zone — "Zones [as shown on plan]: RESIDENTIAL ZONE"
    m = re.search(r"Zones?\s*\[as shown on plan\]\s*:\s*(.+?)$", text, re.MULTILINE)
    result["zone_name"] = m.group(1).strip() if m else None

    # Extract zone_code from zone_name
    if result.get("zone_name"):
        name = result["zone_name"].upper()
        if "RESIDENTIAL" in name:
            result["zone_code"] = "R"
        elif "COMMERCIAL" in name:
            result["zone_code"] = "C"
        elif "INDUSTRIAL" in name:
            result["zone_code"] = "I"
        else:
            result["zone_code"] = None
    else:
        result["zone_code"] = None

    # Reservations
    m = re.search(r"Reservations affecting.*?\]\s*:\s*(.+?)$", text, re.MULTILINE)
    result["reservations_affecting"] = m.group(1).strip() if m else None

    m = re.search(r"Reservations abutting.*?\]\s*:\s*(.+?)$", text, re.MULTILINE)
    result["reservations_abutting"] = m.group(1).strip() if m else None

    # Designations (only in 1991)
    m = re.search(r"Designations affecting.*?\]\s*:\s*(.+?)$", text, re.MULTILINE)
    result["designations_affecting"] = m.group(1).strip() if m else None

    m = re.search(r"Designations abutting.*?\]\s*:\s*(.+?)$", text, re.MULTILINE)
    result["designations_abutting"] = m.group(1).strip() if m else None

    # DP Roads — "D.P. Roads affecting the land[as shown on plan]: EXISTING ROAD  (2)"
    m = re.search(r"D\.?P\.?\s*Roads affecting.*?\]\s*:\s*(.+?)$", text, re.MULTILINE)
    result["dp_roads"] = m.group(1).strip() if m else None

    # RL Remarks — Traffic
    result["rl_remarks_traffic"] = _extract_section(
        text,
        r"REGULAR LINE REMARKS \(Traffic\):",
        r"(?:REGULAR LINE REMARKS \(Survey\)|You are also requested|The above remarks|Demarcation|Note:)",
    )

    # RL Remarks — Survey (not in 1991, but check anyway)
    result["rl_remarks_survey"] = _extract_section(
        text,
        r"REGULAR LINE REMARKS \(Survey\):",
        r"(?:The above remarks|Demarcation|Note:|This is electronically)",
    )

    # Fields not in 1991 format
    result["fp_no"] = None
    result["tps_name"] = None
    result["proposed_road"] = None
    result["proposed_road_widening"] = None
    result["existing_amenities_affecting"] = None
    result["existing_amenities_abutting"] = None
    result["heritage_building"] = None
    result["heritage_precinct"] = None
    result["heritage_buffer_zone"] = None
    result["archaeological_site"] = None
    result["archaeological_buffer"] = None
    result["water_pipeline"] = None
    result["sewer_line"] = None
    result["ground_level"] = None

    # Legacy compatibility fields
    result["dp_remarks"] = result.get("pdf_text", "")[:2000] if result.get("pdf_text") else None
    road_width = _extract_road_width(text)
    result["road_width_m"] = road_width
    result["fsi"] = None
    result["height_limit_m"] = None
    result["reservations"] = _build_reservations_list(result)
    result["crz_zone"] = None
    result["heritage_zone"] = None

    return result


# ── Shared helpers ───────────────────────────────────────────────────────────


def _extract_section(text: str, start_pattern: str, end_pattern: str) -> Optional[str]:
    """Extract text between start_pattern and end_pattern."""
    m = re.search(
        start_pattern + r"\s*(.+?)(?=" + end_pattern + r")",
        text, re.DOTALL | re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    return None


def _extract_road_width(text: str) -> Optional[float]:
    """Try to extract road width in meters from the text."""
    m = re.search(r"(\d+\.?\d*)\s*[Mm](?:\s+(?:wide|road|DP\s*Road))?", text)
    if m:
        val = float(m.group(1))
        if 3.0 <= val <= 60.0:  # reasonable road width
            return val
    return None


def _build_reservations_list(result: dict) -> Optional[list]:
    """Build a reservations list from affecting/abutting fields."""
    items = []
    for key in ("reservations_affecting", "reservations_abutting"):
        val = result.get(key, "")
        if val and val.upper() != "NO":
            items.append(val)
    return items if items else None


def _any_heritage_yes(result: dict) -> Optional[bool]:
    """Return True if any heritage field is 'Yes'."""
    for key in ("heritage_building", "heritage_precinct", "heritage_buffer_zone",
                "archaeological_site", "archaeological_buffer"):
        if result.get(key, "").lower() == "yes":
            return True
    # If all are explicitly "No", return False
    has_any = any(result.get(k) for k in ("heritage_building", "heritage_precinct",
                                           "heritage_buffer_zone", "archaeological_site",
                                           "archaeological_buffer"))
    return False if has_any else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/dp_report_service && python -m pytest tests/test_dp_pdf_parser.py -v`
Expected: All DP 2034 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/dp_report_service/services/dp_pdf_parser.py services/dp_report_service/tests/
git commit -m "feat: add DP Remark PDF parser with DP 2034 format support"
```

---

### Task 3: Add SRDP 1991 Parser Tests

**Files:**
- Modify: `services/dp_report_service/tests/test_dp_pdf_parser.py`

- [ ] **Step 1: Add 1991 format tests**

Append to `services/dp_report_service/tests/test_dp_pdf_parser.py`:

```python
SRDP_1991_PDF = os.path.join(TEST_DOCS, "DP Remark 1991 .pdf")


@pytest.fixture(scope="module")
def srdp_1991_result():
    from services.dp_pdf_parser import parse_dp_pdf
    with open(SRDP_1991_PDF, "rb") as f:
        return parse_dp_pdf(f.read())


@pytest.mark.skipif(
    not os.path.exists(SRDP_1991_PDF),
    reason="Test PDF not found",
)
class TestSRDP1991Parser:
    def test_format_detection(self, srdp_1991_result):
        assert srdp_1991_result["report_type"] == "SRDP_1991"

    def test_reference_no(self, srdp_1991_result):
        assert "SRDP202211111425043" in srdp_1991_result["reference_no"]

    def test_report_date(self, srdp_1991_result):
        assert srdp_1991_result["report_date"] == "04/11/2022"

    def test_applicant_name(self, srdp_1991_result):
        assert "Jinish" in srdp_1991_result["applicant_name"]

    def test_cts_nos(self, srdp_1991_result):
        cts = srdp_1991_result["cts_nos"]
        assert cts is not None
        assert "852" in cts
        assert "854" in cts

    def test_village(self, srdp_1991_result):
        assert "VILE PARLE" in srdp_1991_result["village"]

    def test_ward(self, srdp_1991_result):
        assert srdp_1991_result["ward"] == "K/W"

    def test_zone(self, srdp_1991_result):
        assert "RESIDENTIAL" in srdp_1991_result["zone_name"].upper()
        assert srdp_1991_result["zone_code"] == "R"

    def test_reservations(self, srdp_1991_result):
        assert srdp_1991_result["reservations_affecting"] == "NO"
        assert srdp_1991_result["reservations_abutting"] == "NO"

    def test_designations(self, srdp_1991_result):
        assert srdp_1991_result["designations_affecting"] == "NO"
        assert srdp_1991_result["designations_abutting"] == "NO"

    def test_dp_roads(self, srdp_1991_result):
        assert srdp_1991_result["dp_roads"] is not None
        assert "EXISTING" in srdp_1991_result["dp_roads"]

    def test_rl_remarks_traffic(self, srdp_1991_result):
        rl = srdp_1991_result["rl_remarks_traffic"]
        assert rl is not None
        assert "Traffic" in rl or "traffic" in rl

    def test_2034_fields_are_none(self, srdp_1991_result):
        """1991 format should not have 2034-specific fields."""
        assert srdp_1991_result["fp_no"] is None
        assert srdp_1991_result["water_pipeline"] is None
        assert srdp_1991_result["sewer_line"] is None
        assert srdp_1991_result["ground_level"] is None

    def test_pdf_text_present(self, srdp_1991_result):
        assert srdp_1991_result["pdf_text"] is not None
        assert len(srdp_1991_result["pdf_text"]) > 100


class TestFormatDetection:
    def test_unknown_format_defaults_to_2034(self):
        """Non-DP PDF should be handled gracefully."""
        from services.dp_pdf_parser import parse_dp_pdf
        # Minimal valid PDF with no DP content
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        buf = io.BytesIO()
        writer.write(buf)
        result = parse_dp_pdf(buf.getvalue())
        assert result["report_type"] == "UNKNOWN"

    def test_invalid_pdf_returns_error(self):
        from services.dp_pdf_parser import parse_dp_pdf
        result = parse_dp_pdf(b"not a pdf")
        assert "error" in result


import io  # needed for TestFormatDetection
```

- [ ] **Step 2: Run all tests**

Run: `cd services/dp_report_service && python -m pytest tests/test_dp_pdf_parser.py -v`
Expected: All tests PASS (both 2034 and 1991 classes + format detection).

- [ ] **Step 3: Commit**

```bash
git add services/dp_report_service/tests/test_dp_pdf_parser.py
git commit -m "test: add SRDP 1991 parser tests and format detection tests"
```

---

### Task 4: Extend DPReportResponse Schema

**Files:**
- Modify: `services/dp_report_service/schemas/__init__.py:26-50`

- [ ] **Step 1: Update the schema**

Replace the `DPReportResponse` class in `services/dp_report_service/schemas/__init__.py`:

```python
class DPReportResponse(BaseModel):
    id: Optional[str] = None
    status: DPReportStatus

    # Input echo
    ward: Optional[str] = None
    village: Optional[str] = None
    cts_no: Optional[str] = None

    # ── Report metadata ──────────────────────────────────────────────
    report_type: Optional[str] = None          # "SRDP_1991" or "DP_2034"
    reference_no: Optional[str] = None         # e.g. "SRDP202211111425043"
    report_date: Optional[str] = None          # e.g. "04/11/2022"
    applicant_name: Optional[str] = None       # e.g. "Jinish N Soni"

    # ── Land identification ──────────────────────────────────────────
    cts_nos: Optional[list[str]] = None        # CTS numbers (1991)
    fp_no: Optional[str] = None                # Final Plot number (2034)
    tps_name: Optional[str] = None             # Town Planning Scheme name

    # ── Zoning & classification ──────────────────────────────────────
    zone_code: Optional[str] = None            # e.g. "R", "C1"
    zone_name: Optional[str] = None            # e.g. "Residential(R)"
    road_width_m: Optional[float] = None
    fsi: Optional[float] = None
    height_limit_m: Optional[float] = None

    # ── Reservations & designations ──────────────────────────────────
    reservations: Optional[list[str]] = None
    reservations_affecting: Optional[str] = None
    reservations_abutting: Optional[str] = None
    designations_affecting: Optional[str] = None
    designations_abutting: Optional[str] = None
    existing_amenities_affecting: Optional[str] = None
    existing_amenities_abutting: Optional[str] = None

    # ── Roads ────────────────────────────────────────────────────────
    dp_roads: Optional[str] = None
    proposed_road: Optional[str] = None
    proposed_road_widening: Optional[str] = None

    # ── Regular line remarks ─────────────────────────────────────────
    rl_remarks_traffic: Optional[str] = None
    rl_remarks_survey: Optional[str] = None

    # ── Infrastructure (DP 2034 only) ────────────────────────────────
    water_pipeline: Optional[dict] = None      # {"diameter_mm": int, "distance_m": float}
    sewer_line: Optional[dict] = None          # {"node_no": str, "distance_m": float, "invert_level_m": float}
    ground_level: Optional[dict] = None        # {"min_m": float, "max_m": float, "datum": str}

    # ── Heritage (DP 2034 only) ──────────────────────────────────────
    heritage_building: Optional[str] = None
    heritage_precinct: Optional[str] = None
    heritage_buffer_zone: Optional[str] = None
    archaeological_site: Optional[str] = None
    archaeological_buffer: Optional[str] = None

    # ── Legacy fields ────────────────────────────────────────────────
    crz_zone: Optional[bool] = None
    heritage_zone: Optional[bool] = None
    dp_remarks: Optional[str] = None
    raw_attributes: Optional[dict] = None
    pdf_text: Optional[str] = None

    screenshot_b64: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
```

- [ ] **Step 2: Verify schema loads**

Run: `cd services/dp_report_service && python -c "from schemas import DPReportResponse; print(len(DPReportResponse.model_fields), 'fields'); print('OK')"`
Expected: `~45 fields` and `OK`

- [ ] **Step 3: Commit**

```bash
git add services/dp_report_service/schemas/__init__.py
git commit -m "feat: extend DPReportResponse with DP Remark PDF fields"
```

---

### Task 5: Update Database Schema

**Files:**
- Modify: `services/dp_report_service/services/storage.py:28-67` (`_init_db`)
- Modify: `services/dp_report_service/services/storage.py:102-164` (`update_report`)
- Modify: `services/dp_report_service/services/storage.py:168-189` (`get_report`)

- [ ] **Step 1: Update _init_db with new columns**

Replace the `_init_db` method in `services/dp_report_service/services/storage.py`:

```python
    def _init_db(self):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dp_reports (
                    id              UUID PRIMARY KEY,
                    ward            TEXT NOT NULL,
                    village         TEXT NOT NULL,
                    cts_no          TEXT NOT NULL,
                    lat             DOUBLE PRECISION,
                    lng             DOUBLE PRECISION,
                    zone_code       TEXT,
                    zone_name       TEXT,
                    road_width_m    DOUBLE PRECISION,
                    fsi             DOUBLE PRECISION,
                    height_limit_m  DOUBLE PRECISION,
                    reservations    JSONB,
                    crz_zone        BOOLEAN,
                    heritage_zone   BOOLEAN,
                    dp_remarks      TEXT,
                    raw_attributes  JSONB,
                    map_screenshot  BYTEA,
                    status          VARCHAR(20) DEFAULT 'processing',
                    error_message   TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    -- New fields for DP Remark PDF parsing
                    report_type             VARCHAR(20),
                    reference_no            VARCHAR(100),
                    report_date             VARCHAR(20),
                    applicant_name          VARCHAR(200),
                    cts_nos                 JSONB,
                    fp_no                   VARCHAR(50),
                    tps_name                VARCHAR(200),
                    reservations_affecting  VARCHAR(500),
                    reservations_abutting   VARCHAR(500),
                    designations_affecting  VARCHAR(500),
                    designations_abutting   VARCHAR(500),
                    dp_roads                VARCHAR(500),
                    proposed_road           VARCHAR(200),
                    proposed_road_widening  VARCHAR(200),
                    rl_remarks_traffic      TEXT,
                    rl_remarks_survey       TEXT,
                    water_pipeline          JSONB,
                    sewer_line              JSONB,
                    ground_level            JSONB,
                    heritage_building       VARCHAR(10),
                    heritage_precinct       VARCHAR(10),
                    heritage_buffer_zone    VARCHAR(10),
                    archaeological_site     VARCHAR(10),
                    archaeological_buffer   VARCHAR(10),
                    existing_amenities_affecting VARCHAR(500),
                    existing_amenities_abutting  VARCHAR(500),
                    pdf_text                TEXT,
                    pdf_bytes               BYTEA
                );
            """)
            # Add columns to existing tables (idempotent ALTER)
            new_columns = [
                ("report_type", "VARCHAR(20)"),
                ("reference_no", "VARCHAR(100)"),
                ("report_date", "VARCHAR(20)"),
                ("applicant_name", "VARCHAR(200)"),
                ("cts_nos", "JSONB"),
                ("fp_no", "VARCHAR(50)"),
                ("tps_name", "VARCHAR(200)"),
                ("reservations_affecting", "VARCHAR(500)"),
                ("reservations_abutting", "VARCHAR(500)"),
                ("designations_affecting", "VARCHAR(500)"),
                ("designations_abutting", "VARCHAR(500)"),
                ("dp_roads", "VARCHAR(500)"),
                ("proposed_road", "VARCHAR(200)"),
                ("proposed_road_widening", "VARCHAR(200)"),
                ("rl_remarks_traffic", "TEXT"),
                ("rl_remarks_survey", "TEXT"),
                ("water_pipeline", "JSONB"),
                ("sewer_line", "JSONB"),
                ("ground_level", "JSONB"),
                ("heritage_building", "VARCHAR(10)"),
                ("heritage_precinct", "VARCHAR(10)"),
                ("heritage_buffer_zone", "VARCHAR(10)"),
                ("archaeological_site", "VARCHAR(10)"),
                ("archaeological_buffer", "VARCHAR(10)"),
                ("existing_amenities_affecting", "VARCHAR(500)"),
                ("existing_amenities_abutting", "VARCHAR(500)"),
                ("pdf_text", "TEXT"),
                ("pdf_bytes", "BYTEA"),
            ]
            for col_name, col_type in new_columns:
                try:
                    cur.execute(f"ALTER TABLE dp_reports ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                except Exception:
                    pass  # Column already exists
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_dp_reports_lookup
                ON dp_reports (ward, village, cts_no);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_dp_reports_status
                ON dp_reports (status);
            """)
            conn.commit()
            cur.close()
            conn.close()
            logger.info("dp_reports table ready")
        except Exception as e:
            logger.error("DB init error: %s", e)
```

- [ ] **Step 2: Update update_report with new fields**

Replace the `update_report` method:

```python
    def update_report(self, report_id: str, status: str, **kwargs):
        """Update a DP report with any combination of fields."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            # Build SET clause dynamically from kwargs
            set_parts = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
            values = [status]

            # JSON-serializable fields
            json_fields = {
                "reservations", "raw_attributes", "cts_nos",
                "water_pipeline", "sewer_line", "ground_level",
            }
            # Binary fields
            binary_fields = {"map_screenshot", "pdf_bytes"}
            # All other fields are direct values
            all_fields = {
                "zone_code", "zone_name", "road_width_m", "fsi", "height_limit_m",
                "crz_zone", "heritage_zone", "dp_remarks", "error_message",
                "report_type", "reference_no", "report_date", "applicant_name",
                "fp_no", "tps_name",
                "reservations_affecting", "reservations_abutting",
                "designations_affecting", "designations_abutting",
                "dp_roads", "proposed_road", "proposed_road_widening",
                "rl_remarks_traffic", "rl_remarks_survey",
                "heritage_building", "heritage_precinct", "heritage_buffer_zone",
                "archaeological_site", "archaeological_buffer",
                "existing_amenities_affecting", "existing_amenities_abutting",
                "pdf_text",
            }

            for key, val in kwargs.items():
                if key in json_fields:
                    set_parts.append(f"{key} = %s")
                    values.append(json.dumps(val) if val is not None else None)
                elif key in binary_fields:
                    set_parts.append(f"{key} = %s")
                    values.append(psycopg2.Binary(val) if val else None)
                elif key in all_fields:
                    set_parts.append(f"{key} = %s")
                    values.append(val)

            values.append(report_id)
            sql = f"UPDATE dp_reports SET {', '.join(set_parts)} WHERE id = %s"
            cur.execute(sql, values)
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Updated DP report %s: status=%s", report_id, status)
        except Exception as e:
            logger.error("Failed to update DP report %s: %s", report_id, e)
            raise
```

- [ ] **Step 3: Update get_report to return new fields**

Replace the `get_report` method:

```python
    def get_report(self, report_id: str) -> Optional[dict]:
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT * FROM dp_reports WHERE id = %s",
                (report_id,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error("Failed to get DP report %s: %s", report_id, e)
            return None
```

- [ ] **Step 4: Verify no syntax errors**

Run: `cd services/dp_report_service && python -c "from services.storage import StorageService; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add services/dp_report_service/services/storage.py
git commit -m "feat: extend dp_reports table with DP Remark PDF fields"
```

---

### Task 6: Add /parse-pdf API Endpoint

**Files:**
- Modify: `services/dp_report_service/routers/__init__.py`

- [ ] **Step 1: Add the endpoint**

Add these imports at the top of `services/dp_report_service/routers/__init__.py`:

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from services.dp_pdf_parser import parse_dp_pdf
```

Then add the new endpoint before the `# ── Health` section:

```python
# ── PDF parse endpoint ───────────────────────────────────────────────────────


@router.post("/parse-pdf", response_model=DPReportResponse)
async def parse_dp_pdf_endpoint(file: UploadFile = File(...)):
    """Parse a DP Remark PDF and return extracted data. No browser automation needed."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if len(pdf_bytes) < 100:
        raise HTTPException(status_code=400, detail="PDF file is too small or empty")

    parsed = parse_dp_pdf(pdf_bytes)

    if "error" in parsed and parsed.get("report_type") is None:
        raise HTTPException(status_code=422, detail=parsed["error"])

    return DPReportResponse(
        status=DPReportStatus.COMPLETED,
        ward=parsed.get("ward"),
        village=parsed.get("village"),
        cts_no=None,
        report_type=parsed.get("report_type"),
        reference_no=parsed.get("reference_no"),
        report_date=parsed.get("report_date"),
        applicant_name=parsed.get("applicant_name"),
        cts_nos=parsed.get("cts_nos"),
        fp_no=parsed.get("fp_no"),
        tps_name=parsed.get("tps_name"),
        zone_code=parsed.get("zone_code"),
        zone_name=parsed.get("zone_name"),
        road_width_m=parsed.get("road_width_m"),
        fsi=parsed.get("fsi"),
        height_limit_m=parsed.get("height_limit_m"),
        reservations=parsed.get("reservations"),
        reservations_affecting=parsed.get("reservations_affecting"),
        reservations_abutting=parsed.get("reservations_abutting"),
        designations_affecting=parsed.get("designations_affecting"),
        designations_abutting=parsed.get("designations_abutting"),
        existing_amenities_affecting=parsed.get("existing_amenities_affecting"),
        existing_amenities_abutting=parsed.get("existing_amenities_abutting"),
        dp_roads=parsed.get("dp_roads"),
        proposed_road=parsed.get("proposed_road"),
        proposed_road_widening=parsed.get("proposed_road_widening"),
        rl_remarks_traffic=parsed.get("rl_remarks_traffic"),
        rl_remarks_survey=parsed.get("rl_remarks_survey"),
        water_pipeline=parsed.get("water_pipeline"),
        sewer_line=parsed.get("sewer_line"),
        ground_level=parsed.get("ground_level"),
        heritage_building=parsed.get("heritage_building"),
        heritage_precinct=parsed.get("heritage_precinct"),
        heritage_buffer_zone=parsed.get("heritage_buffer_zone"),
        archaeological_site=parsed.get("archaeological_site"),
        archaeological_buffer=parsed.get("archaeological_buffer"),
        crz_zone=parsed.get("crz_zone"),
        heritage_zone=parsed.get("heritage_zone"),
        dp_remarks=parsed.get("dp_remarks"),
        pdf_text=parsed.get("pdf_text"),
    )
```

- [ ] **Step 2: Verify no syntax errors**

Run: `cd services/dp_report_service && python -c "from routers import router; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/dp_report_service/routers/__init__.py
git commit -m "feat: add POST /parse-pdf endpoint for DP Remark PDF parsing"
```

---

### Task 7: Integration Hook in Scraper

**Files:**
- Modify: `services/dp_report_service/services/dp_scraper.py:428-457`

- [ ] **Step 1: Add parser import and integration hook**

At the top of `services/dp_report_service/services/dp_scraper.py`, add the import:

```python
from .dp_pdf_parser import parse_dp_pdf
```

Then in the `_try_dprmarks_portal` method, after the challan creation block (after line 428), add the PDF integration hook:

```python
        # ── Step 6: Download & parse PDF (when payment automation is ready) ──
        # TODO: Uncomment when browser automation can complete payment and download PDF
        # pdf_bytes = await self._download_report_pdf(page)
        # if pdf_bytes:
        #     parsed = parse_dp_pdf(pdf_bytes)
        #     if parsed.get("report_type"):
        #         return {
        #             "attributes": parsed,
        #             "screenshot_b64": await self._screenshot(page),
        #             "error": None,
        #             "pdf_bytes": pdf_bytes,
        #         }
```

- [ ] **Step 2: Verify no syntax errors**

Run: `cd services/dp_report_service && python -c "from services.dp_scraper import DPBrowserScraper; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/dp_report_service/services/dp_scraper.py
git commit -m "feat: add PDF parse integration hook in DPRMarks portal scraper"
```

---

### Task 8: Final Integration Verification

- [ ] **Step 1: Verify all imports**

Run: `cd services/dp_report_service && python -c "from schemas import DPReportResponse, DPReportStatus; from services.dp_pdf_parser import parse_dp_pdf; from services.storage import StorageService; from routers import router; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 2: Run all tests**

Run: `cd services/dp_report_service && python -m pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Quick manual test with test PDF**

Run:
```bash
cd services/dp_report_service && python -c "
from services.dp_pdf_parser import parse_dp_pdf
import json

with open('../../test_docs/DP Remark 2034 FP 18.pdf', 'rb') as f:
    result = parse_dp_pdf(f.read())

# Print key fields
for k in ['report_type', 'reference_no', 'fp_no', 'ward', 'zone_name', 'dp_roads',
          'water_pipeline', 'sewer_line', 'ground_level', 'reservations_affecting']:
    print(f'{k}: {result.get(k)}')
"
```

Expected output:
```
report_type: DP_2034
reference_no: DP34202211111425031
fp_no: 18
ward: K/W
zone_name: Residential(R)
dp_roads: Existing Road Present
water_pipeline: {'distance_m': 3.44, 'diameter_mm': 250}
sewer_line: {'node_no': '15240911', 'distance_m': 6.82, 'invert_level_m': 28.5}
ground_level: {'min_m': 32.4, 'max_m': 33.0, 'datum': 'THD'}
reservations_affecting: NO
```

- [ ] **Step 4: Commit any remaining changes**

```bash
git add -A services/dp_report_service/
git commit -m "chore: final integration verification for DP Remark PDF parser"
```
