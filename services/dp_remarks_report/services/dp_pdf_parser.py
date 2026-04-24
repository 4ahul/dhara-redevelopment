"""
DP Remark PDF Parser.

Parses MCGM Development Plan remark PDFs into structured data.
Supports both SRDP 1991 (CTS-based) and DP 2034 (CTS/FP-based) formats.
"""

from __future__ import annotations

import io
import re
from typing import Optional

from pypdf import PdfReader


def parse_dp_pdf(pdf_bytes: bytes) -> dict:
    """Parse a DP Remark PDF. Auto-detects SRDP 1991 vs DP 2034.

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        Dict with structured fields extracted from the PDF.
        Always includes 'report_type' and 'pdf_text'.
        On error, returns dict with 'error' key.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        return {"error": f"Failed to read PDF: {exc}", "report_type": "UNKNOWN", "pdf_text": None}

    pages_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)

    full_text = "\n".join(pages_text)

    if not full_text or len(full_text.strip()) < 20:
        return {"report_type": "UNKNOWN", "pdf_text": full_text}

    # Detect format from first 300 chars
    header = full_text[:300]
    if "SRDP" in header:
        return _parse_srdp_1991(full_text)
    elif "DP 2034" in header or "DP2034" in header:
        return _parse_dp_2034(full_text)
    else:
        return {"report_type": "UNKNOWN", "pdf_text": full_text}


# ---------------------------------------------------------------------------
# DP 2034 parser
# ---------------------------------------------------------------------------

def _parse_dp_2034(text: str) -> dict:
    result: dict = {
        "report_type": "DP_2034",
        "pdf_text": text,
    }

    # Reference number: NO. Ch.E./DP34...  or CHE/DP34...
    m = re.search(r"(?:NO\.\s*)?Ch\.E\./?(DP34\d+)", text)
    if m:
        result["reference_no"] = f"Ch.E./{m.group(1)}"
    else:
        m2 = re.search(r"CHE/(DP34\d+)", text)
        result["reference_no"] = f"Ch.E./{m2.group(1)}" if m2 else None

    # Report date: "Payment Dated DD/MM/YYYY" or "Dated: DD/MM/YYYY"
    m = re.search(r"Payment\s+Dated\s+(\d{2}/\d{2}/\d{4})", text)
    if not m:
        m = re.search(r"Dated[:\s]+(\d{2}/\d{2}/\d{4})", text)
    result["report_date"] = m.group(1) if m else None

    # Applicant name: Mr./Mrs. NAME
    m = re.search(r"Mr\./Mrs\.\s*:?\s*(.+?)(?:\n|$)", text)
    result["applicant_name"] = m.group(1).strip() if m else None

    # FP number: F.P. No(s) NN
    m = re.search(r"F\.P\.\s*No\(?s?\)?\s*(\d[\d,\s]*)", text)
    result["fp_no"] = m.group(1).strip() if m else None

    # CTS numbers: "C.T.S. No(s) 1 of DEONAR" or "C.T.S. No(s) 852,853 and 854 of VILLAGE"
    m = re.search(r"C\.T\.S\.\s*No\(?s?\)?\s*([\d,/\s]+(?:\s+and\s+\d+)?)\s+of\s+", text)
    if m:
        raw_nums = m.group(1)
        nums = re.split(r"[,\s]+and\s+|[,\s]+", raw_nums)
        result["cts_nos"] = [n.strip() for n in nums if n.strip()]
    else:
        result["cts_nos"] = None

    # TPS name
    m = re.search(r"(?:TPS|of TPS)\s+([A-Z][A-Z\s.]+?No\.\s*[IVXLCDM]+)", text)
    if not m:
        m = re.search(r"TPS\s+(?:NAME\s+)?([A-Z][A-Z\s.]+?)(?:\s+(?:situated|in)\b)", text)
    result["tps_name"] = m.group(1).strip() if m else None

    # Ward: X/Y Ward  or  referred to Ward X/Y
    m = re.search(r"(?:referred to|in)\s+(?:Ward\s+)?([A-Z]/[A-Z])\s*Ward", text)
    if not m:
        m = re.search(r"(?:referred to Ward|situated in)\s+([A-Z]/[A-Z])", text)
    if not m:
        m = re.search(r"in\s+([A-Z]/[A-Z])\s+[Ww]ard", text)
    result["ward"] = m.group(1).strip() if m else None

    # Village: "of VILLAGE_NAME Village" or from subject line
    m = re.search(r"of\s+([A-Z][A-Z\s]+?)\s+Village", text)
    if not m:
        # Try from TPS line
        m = re.search(r"TPS\s+([A-Z][A-Z\s]+?)(?:\s+No\.)", text)
    result["village"] = m.group(1).strip() if m else None

    # Zone: Zone [as shown on plan] VALUE
    m = re.search(r"Zone\s*\[as shown on plan\]\s*(.+?)(?:\n|EP NO)", text, re.DOTALL)
    if m:
        zone_raw = re.sub(r"\s+", " ", m.group(1)).strip()
        result["zone_name"] = zone_raw
        # Extract zone codes from parens, e.g. Residential(R) -> R
        codes = re.findall(r"\(([A-Z]+)\)", zone_raw)
        result["zone_code"] = ",".join(codes) if codes else None
    else:
        result["zone_name"] = None
        result["zone_code"] = None

    # EP numbers
    ep_matches = re.findall(r"EP\s*NO:\s*(EP-[A-Z]+\d+)", text)
    result["ep_nos"] = sorted(set(ep_matches)) if ep_matches else None

    # SM numbers
    sm_matches = re.findall(r"SM\s*NO:\s*(SM-[A-Z]+\d+)", text)
    result["sm_nos"] = sorted(set(sm_matches)) if sm_matches else None

    # Roads
    m = re.search(r"Existing\s+Road\s+(Present|NIL|No)", text, re.IGNORECASE)
    result["dp_roads"] = m.group(1).strip() if m else None

    m = re.search(r"Proposed\s+Road\s+(.*?)(?:\n|Proposed\s+Road\s+Widening)", text, re.DOTALL)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        result["proposed_road"] = val if val else "NIL"
    else:
        result["proposed_road"] = None

    m = re.search(r"Proposed\s+Road\s+Widening\s+(.*?)(?:\n|Reservation)", text, re.DOTALL)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        result["proposed_road_widening"] = val if val else "NIL"
    else:
        result["proposed_road_widening"] = None

    # Reservations
    m = re.search(r"Reservation\s+affecting\s+the\s+Land\s*\[as shown on plan\]\s*(.+?)(?:\n(?:SM NO|EP NO|Affected|Reservation abutting))", text, re.DOTALL)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        result["reservations_affecting"] = val
    else:
        m2 = re.search(r"Reservation\s+affecting\s+the\s+Land\s*\[as shown on plan\]\s*(NO|NIL|YES)", text, re.IGNORECASE)
        result["reservations_affecting"] = m2.group(1).strip() if m2 else None

    m = re.search(r"Reservation\s+abutting\s+the\s+Land\s*\[as shown on plan\]\s*(.+?)(?:\n|Existing amenities)", text, re.DOTALL)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        result["reservations_abutting"] = val
    else:
        result["reservations_abutting"] = None

    # Existing amenities
    m = re.search(r"Existing\s+amenities\s+affecting\s+the\s+Land\s*\[as shown on\s*plan\]\s*(.+?)(?:\n(?:SM NO|EP NO|Affected|Existing amenities abutting|Corrections))", text, re.DOTALL)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        result["existing_amenities_affecting"] = val
    else:
        m2 = re.search(r"Existing\s+amenities\s+affecting\s+the\s+Land\s*\[as shown on\s*plan\]\s*(NO|NIL|YES)", text, re.IGNORECASE)
        result["existing_amenities_affecting"] = m2.group(1).strip() if m2 else None

    m = re.search(r"Existing\s+amenities\s+abutting\s+the\s+Land\s*\[as shown on\s*plan\]\s*(.+?)(?:\n|Whether|Corrections|Heritage)", text, re.DOTALL)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        result["existing_amenities_abutting"] = val
    else:
        m2 = re.search(r"Existing\s+amenities\s+abutting\s+the\s+Land\s*\[as shown on\s*plan\]\s*(NO|NIL)", text, re.IGNORECASE)
        result["existing_amenities_abutting"] = m2.group(1).strip() if m2 else None

    # Heritage fields
    heritage_questions = [
        ("heritage_building", r"Whether a listed Heritage building[/\s]*site:\s*(Yes|No)\s*/\s*(Yes|No)"),
        ("heritage_precinct", r"Whether situated in a Heritage Precinct:\s*(Yes|No)\s*/\s*(Yes|No)"),
        ("heritage_buffer", r"Whether situated in the buffer zone/Vista of a listed\s*heritage site:\s*(Yes|No)\s*/\s*(Yes|No)"),
        ("archaeological_site", r"Whether a listed archaeological site \(ASI\):\s*(Yes|No)\s*/\s*(Yes|No)"),
        ("archaeological_buffer", r"Whether situated in the buffer zone/Vista of a listed\s*archaeological site \(ASI\):\s*(Yes|No)\s*/\s*(Yes|No)"),
    ]
    # The PDF prints "Yes / No" as both options; actual answer is typically inferred
    # from context. For now store the raw text.
    for key, pattern in heritage_questions:
        m = re.search(pattern, text)
        result[key] = f"{m.group(1)} / {m.group(2)}" if m else None

    # Water pipeline: "Water pipeline near the plot (X.XX meters far) has NNN mm pipe diameter"
    m = re.search(r"Water pipeline near the plot\s*\((\d+\.?\d*)\s*meters?\s*far\)\s*has\s*(\d+)\s*mm\s*pipe diameter", text)
    if m:
        result["water_pipeline"] = {
            "distance_m": float(m.group(1)),
            "diameter_mm": int(m.group(2)),
        }
    else:
        result["water_pipeline"] = None

    # Sewer line: "Sewer Manhole near the plot (Node No. NNNN, X.XX meters far) has invert level XX.XX meters"
    m = re.search(r"Sewer Manhole near the plot\s*\(Node No\.\s*(\d+),\s*(\d+\.?\d*)\s*meters?\s*far\)\s*has\s*invert level\s*(\d+\.?\d*)\s*meters", text)
    if m:
        result["sewer_line"] = {
            "node_no": m.group(1),
            "distance_m": float(m.group(2)),
            "invert_level_m": float(m.group(3)),
        }
    else:
        result["sewer_line"] = None

    # Drainage: "Drain Manhole near the plot (Node ID NNNN, X.XX meters far) has invert level XX.XX meters"
    m = re.search(r"Drain Manhole near the plot\s*\(Node ID\s*(\d+),\s*(\d+\.?\d*)\s*meters?\s*far\)\s*has\s*invert level\s*(\d+\.?\d*)\s*meters", text)
    if m:
        result["drainage"] = {
            "node_id": m.group(1),
            "distance_m": float(m.group(2)),
            "invert_level_m": float(m.group(3)),
        }
    else:
        result["drainage"] = None

    # Ground level: "minimum XX.XX meters and maximum YY.YY meters ground level ... (THD)"
    m = re.search(r"minimum\s+(\d+\.?\d*)\s*meters?\s+and\s+maximum\s+(\d+\.?\d*)\s*meters?\s+ground level.*?(?:Town Hall Datum\s*\((\w+)\)|$)", text, re.DOTALL)
    if m:
        result["ground_level"] = {
            "min_m": float(m.group(1)),
            "max_m": float(m.group(2)),
            "datum": m.group(3) or "THD",
        }
    else:
        result["ground_level"] = None

    # RL Remarks (Traffic)
    m = re.search(r"REGULAR LINE REMARKS \(Traffic\):\s*(.+?)(?=REGULAR LINE REMARKS \(Survey\)|$)", text, re.DOTALL)
    result["rl_remarks_traffic"] = m.group(1).strip() if m else None

    # RL Remarks (Survey)
    m = re.search(r"REGULAR LINE REMARKS \(Survey\):\s*(.+?)(?=Acc:|Note:|The land under reference|Natural Water Course|Pipeline|$)", text, re.DOTALL)
    result["rl_remarks_survey"] = m.group(1).strip() if m else None

    # CRZ zone details
    m = re.search(r"(?:falls under|falls within the Coastal Regulation Zone)\s*(.*?CRZ.*?)(?:Category|$)", text, re.DOTALL)
    if m:
        result["crz_zone_details"] = re.sub(r"\s+", " ", m.group(0)).strip()
    else:
        # Also check for any CRZ mention
        m2 = re.search(r"(?:Coastal Regulation Zone|CRZ)(.+?)(?:Note:|EP-)", text, re.DOTALL)
        result["crz_zone_details"] = re.sub(r"\s+", " ", m2.group(0)).strip() if m2 else None

    # High voltage line
    m = re.search(r"High\s+(?:Tension|Voltage)\s+Power\s+Lines?\s+.+?(?:company|$)", text, re.DOTALL | re.IGNORECASE)
    result["high_voltage_line"] = re.sub(r"\s+", " ", m.group(0)).strip() if m else None

    # Buffer SGNP
    m = re.search(r"Buffer\s+line\s+of\s+SGNP.*?(?:mangrove|swamp).*?(?:\d{4})\.", text, re.DOTALL | re.IGNORECASE)
    if not m:
        m = re.search(r"(?:above land is affected by the Mangrove).*?(?:\d{4})\.", text, re.DOTALL | re.IGNORECASE)
    result["buffer_sgnp"] = re.sub(r"\s+", " ", m.group(0)).strip() if m else None

    # Flamingo ESZ
    m = re.search(r"(?:Buffer Line of Flamingo ESZ|Flamingo Sanctuary).*?(?:construction works|$)\.", text, re.DOTALL | re.IGNORECASE)
    if not m:
        m = re.search(r"Eco-sensitive zone of Thane Creek Flamingo.*?(?:construction works)\.", text, re.DOTALL | re.IGNORECASE)
    result["flamingo_esz"] = re.sub(r"\s+", " ", m.group(0)).strip() if m else None

    # Corrections DCPR 2034
    m = re.search(r"Corrections as per provisions of\s*DCPR 2034:\s*(.+?)(?:Modification|Realignment|Whether|EP NO|$)", text, re.DOTALL)
    result["corrections_dcpr"] = re.sub(r"\s+", " ", m.group(1)).strip() if m else None

    # Modifications Section 37
    m = re.search(r"Modification u/sec 37.*?(?:as shown on plan)\.", text, re.DOTALL)
    result["modifications_sec37"] = re.sub(r"\s+", " ", m.group(0)).strip() if m else None

    # Road realignment
    m = re.search(r"Realignment:.*?(?:approval u/no.*?\d{4})", text, re.DOTALL)
    result["road_realignment"] = re.sub(r"\s+", " ", m.group(0)).strip() if m else None

    return result


# ---------------------------------------------------------------------------
# SRDP 1991 parser
# ---------------------------------------------------------------------------

def _parse_srdp_1991(text: str) -> dict:
    result: dict = {
        "report_type": "SRDP_1991",
        "pdf_text": text,
    }

    # Reference number: No CHE. : SRDPNNN
    m = re.search(r"No\s+CHE\.\s*:\s*(SRDP\d+)", text)
    result["reference_no"] = m.group(1) if m else None

    # Report date
    m = re.search(r"Report\s+Date\s*:\s*(\d{2}/\d{2}/\d{4})", text)
    result["report_date"] = m.group(1) if m else None

    # Applicant name
    m = re.search(r"Mr\./Mrs\.\s*:?\s*(.+?)(?:\n|$)", text)
    result["applicant_name"] = m.group(1).strip() if m else None

    # CTS numbers: "C.T.S. No(s) 852,853,855 and 854 of VILE PARLE"
    m = re.search(r"C\.T\.S\.\s*No\(?s?\)?\s*([\d,/\s]+(?:\s+and\s+\d+)?)\s+of\s+([A-Z][A-Z\s]+?)(?:\s+Village|\s*$)", text, re.MULTILINE)
    if m:
        raw_nums = m.group(1)
        nums = re.split(r"[,\s]+and\s+|[,\s]+", raw_nums)
        result["cts_nos"] = [n.strip() for n in nums if n.strip()]
        result["village"] = m.group(2).strip()
    else:
        result["cts_nos"] = None
        # Village fallback
        m2 = re.search(r"of\s+([A-Z][A-Z\s]+?)\s+Village", text)
        result["village"] = m2.group(1).strip() if m2 else None

    # Ward
    m = re.search(r"referred to ward:\s*([A-Z]/[A-Z])", text)
    if not m:
        m = re.search(r"in\s+([A-Z]/[A-Z])\s+ward", text)
    result["ward"] = m.group(1).strip() if m else None

    # Zone
    m = re.search(r"Zones?\s*\[as shown on plan\]:\s*(.+?)(?:\n|$)", text)
    if m:
        zone_raw = m.group(1).strip()
        result["zone_name"] = zone_raw
        # Extract code from zone name, e.g. "RESIDENTIAL ZONE" -> "R"
        zone_code_map = {
            "RESIDENTIAL": "R",
            "COMMERCIAL": "C",
            "INDUSTRIAL": "I",
        }
        result["zone_code"] = None
        for key, code in zone_code_map.items():
            if key in zone_raw.upper():
                result["zone_code"] = code
                break
    else:
        result["zone_name"] = None
        result["zone_code"] = None

    # Reservations
    m = re.search(r"Reservations\s+affecting\s+the\s+land\[as shown on plan\]:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    result["reservations_affecting"] = m.group(1).strip() if m else None

    m = re.search(r"Reservations\s+abutting\s+the\s+land\[as shown on plan\]:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    result["reservations_abutting"] = m.group(1).strip() if m else None

    # Designations
    m = re.search(r"Designations\s+affecting\s+the\s+land\[as shown on plan\]:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    result["designations_affecting"] = m.group(1).strip() if m else None

    m = re.search(r"Designations\s+abutting\s+the\s+land\[as shown on plan\]:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    result["designations_abutting"] = m.group(1).strip() if m else None

    # DP Roads
    m = re.search(r"D\.P\.\s*Roads\s+affecting\s+the\s+land\[as shown on plan\]:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    result["dp_roads"] = m.group(1).strip() if m else None

    # RL Remarks (Traffic)
    m = re.search(r"REGULAR LINE REMARKS \(Traffic\):\s*(.+?)(?=REGULAR LINE REMARKS|You are also|$)", text, re.DOTALL)
    result["rl_remarks_traffic"] = m.group(1).strip() if m else None

    # Fields that only exist in DP 2034 - set to None
    for key in [
        "fp_no", "tps_name", "proposed_road", "proposed_road_widening",
        "existing_amenities_affecting", "existing_amenities_abutting",
        "heritage_building", "heritage_precinct", "heritage_buffer",
        "archaeological_site", "archaeological_buffer",
        "water_pipeline", "sewer_line", "drainage", "ground_level",
        "rl_remarks_survey", "crz_zone_details", "high_voltage_line",
        "buffer_sgnp", "flamingo_esz", "corrections_dcpr",
        "modifications_sec37", "road_realignment", "ep_nos", "sm_nos",
    ]:
        result[key] = None

    return result

