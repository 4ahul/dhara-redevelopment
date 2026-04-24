"""
DP Report Service — Pydantic Schemas
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DPReportRequest(BaseModel):
    ward: str                       # e.g. "G/S"
    village: str                  # e.g. "WORLI"
    cts_no: str                  # CTS or FP number depending on scheme
    use_fp_scheme: bool = False       # If True, search as FP (2034 scheme) instead of CTS (1991)
    lat: Optional[float] = None    # centroid latitude (from MCGM property lookup)
    lng: Optional[float] = None    # centroid longitude (from MCGM property lookup)


class DPReportStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


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
    cts_nos: Optional[list[str]] = None        # CTS numbers from PDF
    fp_no: Optional[str] = None                # Final Plot number (2034)
    tps_name: Optional[str] = None             # Town Planning Scheme name

    # ── Zoning & classification ──────────────────────────────────────
    zone_code: Optional[str] = None            # e.g. "R", "C1", "NA,R,NDZ,I,SDZ"
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

    # ── Infrastructure (DP 2034) ─────────────────────────────────────
    water_pipeline: Optional[dict] = None      # {"diameter_mm": int, "distance_m": float}
    sewer_line: Optional[dict] = None          # {"node_no": str, "distance_m": float, "invert_level_m": float}
    drainage: Optional[dict] = None            # {"node_id": str, "distance_m": float, "invert_level_m": float}
    ground_level: Optional[dict] = None        # {"min_m": float, "max_m": float, "datum": str}

    # ── Heritage (DP 2034) ───────────────────────────────────────────
    heritage_building: Optional[str] = None
    heritage_precinct: Optional[str] = None
    heritage_buffer_zone: Optional[str] = None
    archaeological_site: Optional[str] = None
    archaeological_buffer: Optional[str] = None

    # ── Environmental & regulatory (DP 2034) ─────────────────────────
    crz_zone_details: Optional[str] = None     # CRZ zone text with categories
    high_voltage_line: Optional[str] = None
    buffer_sgnp: Optional[str] = None          # SGNP/mangrove buffer text
    flamingo_esz: Optional[str] = None         # Flamingo ESZ text

    # ── Modifications & corrections (DP 2034) ────────────────────────
    corrections_dcpr: Optional[str] = None     # DCPR 2034 corrections
    modifications_sec37: Optional[str] = None  # Section 37 modifications
    road_realignment: Optional[str] = None

    # ── EP/SM sheet numbers (DP 2034) ────────────────────────────────
    ep_nos: Optional[list[str]] = None         # e.g. ["EP-ME81", "EP-ME75"]
    sm_nos: Optional[list[str]] = None         # e.g. ["SM-ME21"]

    # ── Legacy fields ────────────────────────────────────────────────
    crz_zone: Optional[bool] = None
    heritage_zone: Optional[bool] = None
    dp_remarks: Optional[str] = None
    pdf_text: Optional[str] = None

    download_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
