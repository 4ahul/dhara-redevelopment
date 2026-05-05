"""PMC Certificate Verification Services

Licensed Surveyor (MCGM AutoDCR SOAP) and Architect (COA portal) verifiers.

Ported with minimal changes from the standalone backend implementation.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from html import unescape
from typing import Any

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# ──────────────────────────────────────────────────────────────────────────────
# Licensed Surveyor (MCGM AutoDCR SOAP)
# ──────────────────────────────────────────────────────────────────────────────

SOAP_URL = "https://autodcr.mcgm.gov.in/BpamsClient/DataServices/ArchSearch.asmx"
TAB_LICENSE_SURVEYOR = "2"
TIMEOUT_S = float(os.environ.get("SCRAPE_TIMEOUT_MS", "45000")) / 1000

SOAP_BODY_TEMPLATE = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
    'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">\n'
    "  <soap:Body>\n"
    '    <GetGridData xmlns="TreeGrid">\n'
    "      <tabValue>{tab}</tabValue>\n"
    "    </GetGridData>\n"
    "  </soap:Body>\n"
    "</soap:Envelope>"
)

_ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
_ITEM_RE = re.compile(r"<I\s+([^>]*?)/>")
_RESULT_RE = re.compile(r"<GetGridDataResult>([\s\S]*?)</GetGridDataResult>")


def _normalize_reg_no(s: Any) -> str:
    return re.sub(r"\s+", "", (str(s) if s is not None else "").strip().upper())


def _parse_attributes(tag_inner: str) -> dict:
    return {m.group(1): unescape(m.group(2)) for m in _ATTR_RE.finditer(tag_inner)}


def _extract_rows(soap_xml: str) -> list[dict]:
    m = _RESULT_RE.search(soap_xml)
    if not m:
        return []
    inner = unescape(m.group(1))
    return [_parse_attributes(row.group(1)) for row in _ITEM_RE.finditer(inner)]


def _row_to_consultant(row: dict) -> dict:
    return {
        "name": (row.get("Nm") or "").strip(),
        "registrationNumber": row.get("RNo", ""),
        "validUpto": row.get("Val", ""),
        "firm": ((row.get("Frm") or "").strip() or None),
        "qualification": ((row.get("Qlf") or "").strip() or None),
        "address": row.get("Add") or None,
        "city": row.get("Cty") or None,
        "state": row.get("Sat") or None,
        "mobile": row.get("Mob") or None,
        "email": row.get("EId") or None,
    }


def _is_still_valid(valid_upto: str | None) -> bool | None:
    if not valid_upto:
        return None
    try:
        d = date_parser.parse(valid_upto, dayfirst=True, fuzzy=True)
    except (ValueError, TypeError, OverflowError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.timestamp() >= datetime.now(UTC).timestamp()


async def _fetch_grid_data(tab: str) -> str:
    body = SOAP_BODY_TEMPLATE.format(tab=tab)
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        r = await client.post(
            SOAP_URL,
            content=body,
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "TreeGrid/GetGridData",
                "User-Agent": "Mozilla/5.0 Dhara-Orchestrator/3.0",
            },
        )
    if r.status_code != 200:
        raise RuntimeError(f"Upstream returned {r.status_code}")
    return r.text


async def verify_licensed_surveyor(registration_number: str) -> dict:
    target = _normalize_reg_no(registration_number)
    if not target:
        return {"valid": False, "reason": "empty_registration_number"}

    soap_xml = await _fetch_grid_data(TAB_LICENSE_SURVEYOR)
    rows = _extract_rows(soap_xml)
    if not rows:
        return {"valid": False, "reason": "upstream_empty", "total": 0}

    match = next((r for r in rows if _normalize_reg_no(r.get("RNo")) == target), None)
    if not match:
        return {
            "valid": False,
            "reason": "not_found",
            "total": len(rows),
            "message": f"No Licensed Surveyor found with registration number {registration_number}",
        }

    consultant = _row_to_consultant(match)
    still_valid = _is_still_valid(consultant.get("validUpto"))

    return {
        "valid": still_valid is not False,
        "expired": still_valid is False,
        "consultant": consultant,
        "total": len(rows),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Architect (Council of Architecture)
# ──────────────────────────────────────────────────────────────────────────────

COA_URL = "https://www.coa.gov.in/ver_arch.php?lang=1"


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "").lower()


def _extract_data_row(html: str, registration_number: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    target = _norm(registration_number)
    for tr in soup.select("tr.search_archpannel_tabletr_text"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) <= 1:
            continue  # colspan 'NO Record Found !' row
        reg_cell = cells[2] if len(cells) > 2 else ""
        if _norm(reg_cell) == target:
            return {
                "srNo": cells[0] if len(cells) > 0 else None,
                "name": cells[1] if len(cells) > 1 else None,
                "registrationNumber": reg_cell,
                "status": cells[3] if len(cells) > 3 else None,
                "validUpto": cells[4] if len(cells) > 4 else None,
                "city": cells[5] if len(cells) > 5 else None,
                "disciplinary": cells[6] if len(cells) > 6 else None,
            }
    return None


_NO_RECORD_RE = re.compile(
    r"search_archpannel_tabletr_text[\s\S]*?colspan[\s\S]*?NO\s*Record\s*Found", re.I
)


def _is_no_record(html: str) -> bool:
    return bool(_NO_RECORD_RE.search(html))


async def verify_architect(registration_number: str) -> dict:
    if not registration_number:
        return {
            "valid": False,
            "reason": "invalid_input",
            "message": "Registration number is required.",
        }

    data = {"reg_no": registration_number, "cap_code2": "", "T33": "", "Search": "Search"}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Referer": COA_URL,
        "Origin": "https://www.coa.gov.in",
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            r = await client.post(COA_URL, data=data, headers=headers)
    except Exception as e:
        return {
            "valid": False,
            "reason": "upstream_error",
            "message": str(e) or "COA submit failed",
        }

    if r.status_code != 200:
        return {
            "valid": False,
            "reason": "upstream_error",
            "message": f"COA returned {r.status_code}",
        }

    html = r.text
    row = _extract_data_row(html, registration_number)
    if row:
        return {
            "valid": True,
            "details": {
                "name": row["name"],
                "registrationNumber": row["registrationNumber"],
                "status": row["status"],
                "validUpto": row["validUpto"],
                "city": row["city"],
                "disciplinary": row["disciplinary"],
            },
        }

    if _is_no_record(html):
        return {
            "valid": False,
            "reason": "not_found",
            "message": f"No registered architect found for {registration_number}.",
        }

    return {
        "valid": False,
        "reason": "unknown_response",
        "message": "Could not parse the COA response. Please try again.",
    }
