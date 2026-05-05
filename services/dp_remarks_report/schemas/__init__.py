"""
DP Report Service — Pydantic Schemas
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class DPReportRequest(BaseModel):
    ward: str  # e.g. "G/S"
    village: str  # e.g. "WORLI"
    cts_no: str  # CTS or FP number depending on scheme
    use_fp_scheme: bool = False  # If True, go directly to FP path (skip CTS attempt)
    tps_scheme: str | None = None  # TPS scheme name for FP path, e.g. "VILE PARLE (E) No. I"
    fp_no: str | None = None  # Explicit FP number if different from cts_no
    lat: float | None = None  # centroid latitude (from MCGM property lookup)
    lng: float | None = None  # centroid longitude (from MCGM property lookup)


class DPReportStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DPReportResponse(BaseModel):
    id: str | None = None
    status: DPReportStatus

    # Input echo
    ward: str | None = None
    village: str | None = None
    cts_no: str | None = None

    # ── Report metadata ──────────────────────────────────────────────
    report_type: str | None = None  # "SRDP_1991" or "DP_2034"
    reference_no: str | None = None  # e.g. "SRDP202211111425043"
    report_date: str | None = None  # e.g. "04/11/2022"
    applicant_name: str | None = None  # e.g. "Jinish N Soni"

    # ── Land identification ──────────────────────────────────────────
    cts_nos: list[str] | None = None  # CTS numbers from PDF
    fp_no: str | None = None  # Final Plot number (2034)
    tps_name: str | None = None  # Town Planning Scheme name

    # ── Zoning & classification ──────────────────────────────────────
    zone_code: str | None = None  # e.g. "R", "C1", "NA,R,NDZ,I,SDZ"
    zone_name: str | None = None  # e.g. "Residential(R)"
    road_width_m: float | None = None
    fsi: float | None = None
    height_limit_m: float | None = None

    # ── Reservations & designations ──────────────────────────────────
    reservations: list[str] | None = None
    reservations_affecting: str | None = None
    reservations_abutting: str | None = None
    designations_affecting: str | None = None
    designations_abutting: str | None = None
    existing_amenities_affecting: str | None = None
    existing_amenities_abutting: str | None = None

    # ── Roads ────────────────────────────────────────────────────────
    dp_roads: str | None = None
    proposed_road: str | None = None
    proposed_road_widening: str | None = None

    # ── Regular line remarks ─────────────────────────────────────────
    rl_remarks_traffic: str | None = None
    rl_remarks_survey: str | None = None

    # ── Infrastructure (DP 2034) ─────────────────────────────────────
    water_pipeline: dict | None = None  # {"diameter_mm": int, "distance_m": float}
    sewer_line: dict | None = None  # {"node_no": str, "distance_m": float, "invert_level_m": float}
    drainage: dict | None = None  # {"node_id": str, "distance_m": float, "invert_level_m": float}
    ground_level: dict | None = None  # {"min_m": float, "max_m": float, "datum": str}

    # ── Heritage (DP 2034) ───────────────────────────────────────────
    heritage_building: str | None = None
    heritage_precinct: str | None = None
    heritage_buffer_zone: str | None = None
    archaeological_site: str | None = None
    archaeological_buffer: str | None = None

    # ── Environmental & regulatory (DP 2034) ─────────────────────────
    crz_zone_details: str | None = None  # CRZ zone text with categories
    high_voltage_line: str | None = None
    buffer_sgnp: str | None = None  # SGNP/mangrove buffer text
    flamingo_esz: str | None = None  # Flamingo ESZ text

    # ── Modifications & corrections (DP 2034) ────────────────────────
    corrections_dcpr: str | None = None  # DCPR 2034 corrections
    modifications_sec37: str | None = None  # Section 37 modifications
    road_realignment: str | None = None

    # ── EP/SM sheet numbers (DP 2034) ────────────────────────────────
    ep_nos: list[str] | None = None  # e.g. ["EP-ME81", "EP-ME75"]
    sm_nos: list[str] | None = None  # e.g. ["SM-ME21"]

    # ── Area metrics (DP 2034) ───────────────────────────────────────
    reservation_area_sqm: float | None = None  # total area under reservation within plot (sqm)
    amenity_area_sqm: float | None = None  # total area of existing amenities within plot (sqm)
    setback_area_sqm: float | None = None  # area under road setback/widening within plot (sqm)

    # ── Legacy fields ────────────────────────────────────────────────
    crz_zone: bool | None = None
    heritage_zone: bool | None = None
    dp_remarks: str | None = None
    pdf_text: str | None = None

    download_url: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
