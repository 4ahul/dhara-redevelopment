"""
Cell Mapper Service
Maps microservice output data to specific yellow cells in the Excel templates.

Each yellow cell in the template is an INPUT cell — Excel formulas in other cells
reference these inputs to auto-compute the entire feasibility report.

IMPORTANT: Cells whose current_value starts with '=' are FORMULAS — they MUST NOT
be overwritten.  Only cells with literal values (numbers, strings, blanks) should
be set.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CellMapping:
    """Maps a data source to a yellow cell in the Excel template."""

    sheet: str
    cell: str
    data_path: str  # dot notation: "premium.rr_open_land_sqm" or top-level "num_flats"
    transform: str = "direct"  # direct | float | int | str | bool_toggle
    default: Any = None  # fallback value when data_path resolves to None
    is_formula: bool = False  # True → never overwrite this cell


# ────────────────────────────────────────────────────────────────────────────
# CORRECT MAPPINGS — derived from manual examination of the actual templates
# ────────────────────────────────────────────────────────────────────────────

# Shared base mappings used by both templates (30(A)/33(7)(B) and 33(20)(B))
_DETAILS_COMMON: list[CellMapping] = [
    # ── Plot & Site Data ──────────────────────────────────────────────────
    CellMapping("Details", "P4", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "Q4", "dp_report.amenity_area_sqm", "float", 0),
    CellMapping("Details", "P7", "dp_report.setback_area_sqm", "float", 0),
    CellMapping("Details", "N17", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details", "R17", "dp_report.road_width_m|road_width_m", "float", 18.3),
    CellMapping("Details", "B19", "manual_inputs.protected_area_sqm", "float", 0),
    CellMapping("Details", "N20", "manual_inputs.old_setback_sqm", "float", 0),
    # ── NOC Toggles (0=not needed, 1=needed) ──────────────────────────────
    CellMapping("Details", "R28", "manual_inputs.noc_railway", "int", 0),
    CellMapping("Details", "R31", "manual_inputs.noc_civil_aviation", "int", 0),
    # ── Existing Areas ────────────────────────────────────────────────────
    CellMapping("Details", "O32", "manual_inputs.existing_residential_bua_sqm", "float", 0),
    CellMapping("Details", "O33", "manual_inputs.existing_commercial_bua_sqm", "float", 0),
    CellMapping("Details", "G34", "manual_inputs.commercial_extra_multiplier", "float", 1.28),
    CellMapping("Details", "G39", "manual_inputs.residential_extra_multiplier", "float", 1.30),
    # ── RR Rates & Road Frontage ──────────────────────────────────────────
    CellMapping("Details", "O40", "manual_inputs.plot_road_length_m", "float", 100),
    CellMapping(
        "Details",
        "J54",
        "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm",
        "float",
        128870,
    ),
    # ── Society Details: Existing Carpet Areas ────────────────────────────
    CellMapping("Details", "N47", "existing_commercial_carpet_sqft", "float", 0),
    CellMapping("Details", "Q47", "existing_residential_carpet_sqft", "float", 22305),
    # ── Tenement Counts ───────────────────────────────────────────────────
    CellMapping("Details", "N49", "num_commercial", "int", 12),
    CellMapping("Details", "P49", "num_flats", "int", 138),
    # ── Rent Rates (₹/sqft/month) ─────────────────────────────────────────
    CellMapping("Details", "O50", "manual_inputs.rent_commercial", "float", 150),
    CellMapping("Details", "Q50", "manual_inputs.rent_residential", "float", 125),
    # ── Corpus Fund (₹/sqft) ──────────────────────────────────────────────
    CellMapping("Details", "O51", "manual_inputs.corpus_commercial", "float", 1500),
    CellMapping("Details", "Q51", "manual_inputs.corpus_residential", "float", 1500),
    # ── Brokerage & Shifting (₹ per member, one-time) ─────────────────────
    CellMapping("Details", "O52", "manual_inputs.brokerage_commercial", "float", 125),
    CellMapping("Details", "Q52", "manual_inputs.brokerage_residential", "float", 125),
    CellMapping("Details", "O53", "manual_inputs.shifting_commercial", "float", 30000),
    CellMapping("Details", "Q53", "manual_inputs.shifting_residential", "float", 30000),
    # ── Ready Reckoner Land Rate ──────────────────────────────────────────
    # Removed duplicate J54 entry
    # ── Period of Completion (months) ─────────────────────────────────────
    CellMapping("Details", "Q55", "manual_inputs.completion_months_residential", "float", 36),
]

_CONSTRUCTION_COST_COMMON: list[CellMapping] = [
    CellMapping("Construction Cost", "D8", "manual_inputs.const_rate_commercial", "float", 3600),
    CellMapping("Construction Cost", "D12", "manual_inputs.const_rate_residential", "float", 3600),
    CellMapping("Construction Cost", "D15", "manual_inputs.const_rate_podium", "float", 2200),
]

_MCGM_COMMON: list[CellMapping] = [
    CellMapping("MCGM PAYMENTS", "D5", "manual_inputs.scrutiny_rate_1", "float", 156),
]

# 33(20)(B) has TDR rate cells + different row offsets in MCGM PAYMENTS
_MCGM_2020B_EXTRA: list[CellMapping] = []

# STAMP DUTY: B44 = formula (Details!N55+Details!P55), skip

_SUMMARY1_COMMON: list[CellMapping] = [
    CellMapping("SUMMARY 1", "D75", "manual_inputs.toggle_section_75", "int", 1),
    CellMapping("SUMMARY 1", "I87", "manual_inputs.land_acquisition_cost", "float", 0),
]

_PNL_COMMON: list[CellMapping] = [
    CellMapping(
        "Profit & Loss Statement", "D19", "financial.sale_rate_commercial_gf", "float", 75000
    ),
    CellMapping(
        "Profit & Loss Statement", "D20", "financial.sale_rate_commercial_1f", "float", 60000
    ),
    CellMapping(
        "Profit & Loss Statement",
        "D28",
        "financial.sale_rate_residential|sale_rate_per_sqft",
        "float",
        50000,
    ),
    CellMapping(
        "Profit & Loss Statement", "C30", "manual_inputs.parking_units_for_sale", "int", 75
    ),
    CellMapping(
        "Profit & Loss Statement", "D30", "financial.parking_price_per_unit", "float", 1200000
    ),
]


# 33(20)(B) SUMMARY 1 has different row numbers for some cells
_SUMMARY1_2020B: list[CellMapping] = [
    CellMapping("SUMMARY 1", "D75", "manual_inputs.toggle_section_75", "int", 1),
    CellMapping("SUMMARY 1", "D77", "manual_inputs.toggle_section_77", "int", 1),
    CellMapping("SUMMARY 1", "D84", "manual_inputs.toggle_section_84", "int", 1),
    CellMapping("SUMMARY 1", "D86", "manual_inputs.toggle_section_86", "int", 1),
    CellMapping("SUMMARY 1", "I87", "manual_inputs.land_acquisition_cost", "float", 0),
    CellMapping("SUMMARY 1", "I105", "manual_inputs.estate_noc_premium", "float", 0),
    CellMapping("SUMMARY 1", "I108", "manual_inputs.estate_lease_premium", "float", 0),
    CellMapping("SUMMARY 1", "I119", "manual_inputs.acquisition_brokerage", "float", 0),
    CellMapping("SUMMARY 1", "I122", "manual_inputs.donations_misc", "float", 500000),
    CellMapping("SUMMARY 1", "I124", "manual_inputs.special_approval_1", "float", 2500000),
    CellMapping("SUMMARY 1", "I125", "manual_inputs.special_approval_2", "float", 20000000),
    # I116 is a formula in 33(20)(B) — do NOT map it
]


# ────────────────────────────────────────────────────────────────────────────
# 33(12)(B) CLUBBING — Reg. 30(A), 33(7)(B), 33(12)B, 33(20)(B)
# Cells shifted vs base template due to extra regulation rows in Details
# ────────────────────────────────────────────────────────────────────────────

_DETAILS_33_12B: list[CellMapping] = [
    CellMapping("Details", "P5", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "Q5", "dp_report.amenity_area_sqm", "float", 0),
    CellMapping("Details", "P8", "dp_report.setback_area_sqm", "float", 0),
    CellMapping("Details", "N19", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details", "R19", "dp_report.road_width_m|road_width_m", "float", 18.3),
    CellMapping("Details", "J22", "manual_inputs.protected_area_sqm", "float", 0),
    CellMapping("Details", "N22", "manual_inputs.old_setback_sqm", "float", 0),
    # NOC toggles — shifted range R27–R37
    CellMapping("Details", "R27", "manual_inputs.noc_highway", "int", 0),
    CellMapping("Details", "R28", "manual_inputs.noc_mmrda", "int", 0),
    CellMapping("Details", "R32", "manual_inputs.noc_railway", "int", 0),
    CellMapping("Details", "R33", "manual_inputs.noc_asi", "int", 0),
    CellMapping("Details", "R34", "manual_inputs.noc_mhcc", "int", 0),
    CellMapping("Details", "R35", "manual_inputs.noc_civil_aviation", "int", 0),
    CellMapping("Details", "R36", "dp_report.crz_zone", "bool_toggle", 0),
    CellMapping("Details", "R37", "manual_inputs.noc_other", "int", 0),
    CellMapping("Details", "G38", "manual_inputs.commercial_extra_multiplier", "float", 1.35),
    CellMapping("Details", "G45", "manual_inputs.residential_extra_multiplier", "float", 2.08),
    CellMapping("Details", "O46", "manual_inputs.plot_road_length_m", "float", 0),
    CellMapping(
        "Details",
        "P46",
        "ready_reckoner.rr_residential_sqm|premium.rr_residential_sqm",
        "float",
        180000,
    ),
    CellMapping(
        "Details",
        "Q46",
        "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm",
        "float",
        461400,
    ),
    CellMapping("Details", "J53", "manual_inputs.sale_commercial_bua_sqm", "float", 0),
    CellMapping("Details", "O55", "existing_commercial_carpet_sqft", "float", 0),
    CellMapping("Details", "Q55", "existing_residential_carpet_sqft", "float", 17716),
    CellMapping("Details", "N57", "num_commercial", "int", 0),
    CellMapping("Details", "P57", "num_flats", "int", 36),
    CellMapping("Details", "O58", "manual_inputs.rent_commercial", "float", 0),
    CellMapping("Details", "Q58", "manual_inputs.rent_residential", "float", 280),
    CellMapping("Details", "O59", "manual_inputs.corpus_commercial", "float", 0),
    CellMapping("Details", "Q59", "manual_inputs.corpus_residential", "float", 6300),
    CellMapping("Details", "O60", "manual_inputs.brokerage_commercial", "float", 0),
    CellMapping("Details", "Q60", "manual_inputs.brokerage_residential", "float", 100000),
    CellMapping("Details", "O61", "manual_inputs.shifting_commercial", "float", 0),
    CellMapping("Details", "Q61", "manual_inputs.shifting_residential", "float", 70000),
    CellMapping("Details", "O63", "manual_inputs.deposit_commercial", "float", 0),
    CellMapping("Details", "Q63", "manual_inputs.deposit_residential", "float", 0),
    CellMapping("Details", "O64", "manual_inputs.completion_months_commercial", "float", 0),
    CellMapping("Details", "Q64", "manual_inputs.completion_months_residential", "float", 42),
    CellMapping("Details", "N74", "manual_inputs.osd_ratio", "float", 0.7),
    CellMapping("Details", "N75", "manual_inputs.staircase_ratio", "float", 0.35),
    CellMapping("Details", "O76", "manual_inputs.construction_area_multiplier", "float", 1.5),
    CellMapping("Details", "N77", "manual_inputs.podium_ratio", "float", 0.6),
    CellMapping("Details", "O77", "manual_inputs.podium_floors", "int", 4),
    CellMapping("Details", "N78", "manual_inputs.basement_ratio", "float", 0.4),
    CellMapping("Details", "O78", "manual_inputs.basement_count", "int", 3),
]

_CONSTRUCTION_COST_33_12B: list[CellMapping] = [
    CellMapping("Construction Cost", "D8", "manual_inputs.const_rate_commercial", "float", 3800),
    CellMapping("Construction Cost", "D12", "manual_inputs.const_rate_residential", "float", 4000),
    CellMapping("Construction Cost", "D15", "manual_inputs.const_rate_podium", "float", 1800),
    CellMapping("Construction Cost", "F21", "manual_inputs.const_rate_basement", "float", 2000),
    CellMapping("Construction Cost", "F27", "manual_inputs.excavation_rate_brass", "float", 1350),
]

_MCGM_33_12B: list[CellMapping] = [
    CellMapping("MCGM PAYMENTS", "D5", "manual_inputs.scrutiny_rate_1", "float", 156),
    CellMapping("MCGM PAYMENTS", "D7", "manual_inputs.scrutiny_rate_2", "float", 156),
    CellMapping("MCGM PAYMENTS", "C220", "manual_inputs.slum_tdr_rate", "float", 0.9),
    CellMapping("MCGM PAYMENTS", "C225", "manual_inputs.gen_tdr_rate", "float", 0.65),
    CellMapping("MCGM PAYMENTS", "J278", "manual_inputs.pco_rate", "float", 10),
]

_SUMMARY1_33_12B: list[CellMapping] = [
    CellMapping("SUMMARY 1", "D75", "manual_inputs.toggle_section_75", "int", 1),
    CellMapping("SUMMARY 1", "D77", "manual_inputs.toggle_section_77", "int", 1),
    CellMapping("SUMMARY 1", "D84", "manual_inputs.toggle_section_84", "int", 1),
    CellMapping("SUMMARY 1", "D86", "manual_inputs.toggle_section_86", "int", 1),
    CellMapping("SUMMARY 1", "I87", "manual_inputs.land_acquisition_cost", "float", 0),
    CellMapping("SUMMARY 1", "I116", "manual_inputs.donations_misc", "float", 0),
    CellMapping("SUMMARY 1", "I118", "manual_inputs.special_approval_1", "float", 2500000),
    CellMapping("SUMMARY 1", "I119", "manual_inputs.special_approval_2", "float", 20000000),
]

_PNL_33_12B: list[CellMapping] = [
    CellMapping(
        "Profit & Loss Statement", "D19", "financial.sale_rate_commercial_gf", "float", 75000
    ),
    CellMapping(
        "Profit & Loss Statement", "D20", "financial.sale_rate_commercial_1f", "float", 60000
    ),
    CellMapping("Profit & Loss Statement", "C21", "manual_inputs.commercial_2f_area", "float", 0),
    CellMapping("Profit & Loss Statement", "D21", "financial.sale_rate_commercial_2f", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D22", "financial.sale_rate_commercial_other", "float", 0
    ),
    CellMapping(
        "Profit & Loss Statement",
        "D28",
        "financial.sale_rate_residential|sale_rate_per_sqft",
        "float",
        100000,
    ),
    CellMapping(
        "Profit & Loss Statement", "C30", "manual_inputs.parking_units_for_sale", "int", 50
    ),
    CellMapping(
        "Profit & Loss Statement", "D30", "financial.parking_price_per_unit", "float", 2500000
    ),
]


# ────────────────────────────────────────────────────────────────────────────
# 33(7)(A) CLUBBING — Reg. 30(A), 33(7)(A), 33(12)B, 33(20)(B)
# Similar to 33(12)(B) CLUBBING but uses 33(7)(A) sub-scheme
# ────────────────────────────────────────────────────────────────────────────

_DETAILS_33_7A: list[CellMapping] = [
    CellMapping("Details", "P5", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "Q5", "dp_report.amenity_area_sqm", "float", 0),
    CellMapping("Details", "P8", "dp_report.setback_area_sqm", "float", 0),
    CellMapping("Details", "N19", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details", "R19", "dp_report.road_width_m|road_width_m", "float", 13.4),
    CellMapping("Details", "J22", "manual_inputs.protected_area_sqm", "float", 0),
    CellMapping("Details", "N22", "manual_inputs.old_setback_sqm", "float", 0),
    CellMapping("Details", "G38", "manual_inputs.commercial_extra_multiplier", "float", 1),
    CellMapping("Details", "G45", "manual_inputs.residential_extra_multiplier", "float", 1.1),
    CellMapping("Details", "O46", "manual_inputs.plot_road_length_m", "float", 0),
    CellMapping(
        "Details",
        "P46",
        "ready_reckoner.rr_residential_sqm|premium.rr_residential_sqm",
        "float",
        100000,
    ),
    CellMapping(
        "Details",
        "Q46",
        "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm",
        "float",
        160160,
    ),
    CellMapping("Details", "J53", "manual_inputs.sale_commercial_bua_sqm", "float", 110),
    CellMapping("Details", "O55", "existing_commercial_carpet_sqft", "float", 0),
    CellMapping("Details", "N57", "num_commercial", "int", 0),
    CellMapping("Details", "P57", "num_flats", "int", 13),
    CellMapping("Details", "O58", "manual_inputs.rent_commercial", "float", 0),
    CellMapping("Details", "Q58", "manual_inputs.rent_residential", "float", 65),
    CellMapping("Details", "O59", "manual_inputs.corpus_commercial", "float", 0),
    CellMapping("Details", "Q59", "manual_inputs.corpus_residential", "float", 0),
    CellMapping("Details", "O60", "manual_inputs.brokerage_commercial", "float", 0),
    CellMapping("Details", "Q60", "manual_inputs.brokerage_residential", "float", 20000),
    CellMapping("Details", "O61", "manual_inputs.shifting_commercial", "float", 0),
    CellMapping("Details", "Q61", "manual_inputs.shifting_residential", "float", 10000),
    CellMapping(
        "Details", "J63", "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm", "float", 65180
    ),
    CellMapping("Details", "O63", "manual_inputs.deposit_commercial", "float", 0),
    CellMapping("Details", "Q63", "manual_inputs.deposit_residential", "float", 0),
    CellMapping("Details", "O64", "manual_inputs.completion_months_commercial", "float", 0),
    CellMapping("Details", "Q64", "manual_inputs.completion_months_residential", "float", 36),
    CellMapping("Details", "N74", "manual_inputs.osd_ratio", "float", 0.4),
    CellMapping("Details", "N75", "manual_inputs.staircase_ratio", "float", 0.25),
    CellMapping("Details", "O76", "manual_inputs.construction_area_multiplier", "float", 1.4),
    CellMapping("Details", "N77", "manual_inputs.podium_ratio", "float", 0.6),
    CellMapping("Details", "O77", "manual_inputs.podium_floors", "int", 0),
    CellMapping("Details", "N78", "manual_inputs.basement_ratio", "float", 0.4),
    CellMapping("Details", "O78", "manual_inputs.basement_count", "int", 1),
]

_CONSTRUCTION_COST_33_7A: list[CellMapping] = [
    CellMapping("Construction Cost", "D8", "manual_inputs.const_rate_commercial", "float", 3800),
    CellMapping("Construction Cost", "D12", "manual_inputs.const_rate_residential", "float", 3800),
    CellMapping("Construction Cost", "D15", "manual_inputs.const_rate_podium", "float", 1800),
    CellMapping("Construction Cost", "H21", "manual_inputs.const_rate_basement", "float", 2000),
    CellMapping("Construction Cost", "F27", "manual_inputs.excavation_rate_brass", "float", 1350),
]

_MCGM_33_7A: list[CellMapping] = [
    CellMapping("MCGM PAYMENTS", "D5", "manual_inputs.scrutiny_rate_1", "float", 156),
    CellMapping("MCGM PAYMENTS", "D7", "manual_inputs.scrutiny_rate_2", "float", 156),
    CellMapping("MCGM PAYMENTS", "C220", "manual_inputs.slum_tdr_rate", "float", 0.9),
    CellMapping("MCGM PAYMENTS", "C225", "manual_inputs.gen_tdr_rate", "float", 0.65),
]

_SUMMARY1_33_7A: list[CellMapping] = [
    CellMapping("SUMMARY 1", "D75", "manual_inputs.toggle_section_75", "int", 1),
    CellMapping("SUMMARY 1", "D77", "manual_inputs.toggle_section_77", "int", 1),
    CellMapping("SUMMARY 1", "D84", "manual_inputs.toggle_section_84", "int", 1),
    CellMapping("SUMMARY 1", "D86", "manual_inputs.toggle_section_86", "int", 1),
    CellMapping("SUMMARY 1", "I109", "manual_inputs.land_acquisition_cost", "float", 10000000),
    CellMapping("SUMMARY 1", "I115", "manual_inputs.donations_misc", "float", 0),
    CellMapping("SUMMARY 1", "I117", "manual_inputs.special_approval_1", "float", 0),
    CellMapping("SUMMARY 1", "I118", "manual_inputs.special_approval_2", "float", 0),
]

_PNL_33_7A: list[CellMapping] = [
    CellMapping(
        "Profit & Loss Statement", "D19", "financial.sale_rate_commercial_gf", "float", 60000
    ),
    CellMapping("Profit & Loss Statement", "C21", "manual_inputs.commercial_2f_area", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D22", "financial.sale_rate_commercial_other", "float", 0
    ),
    CellMapping(
        "Profit & Loss Statement",
        "D28",
        "financial.sale_rate_residential|sale_rate_per_sqft",
        "float",
        25000,
    ),
    CellMapping(
        "Profit & Loss Statement", "C30", "manual_inputs.parking_units_for_sale", "int", 25
    ),
    CellMapping(
        "Profit & Loss Statement", "D30", "financial.parking_price_per_unit", "float", 1000000
    ),
]


# ────────────────────────────────────────────────────────────────────────────
# INSITU 30(A)/33(7)(B) — Reg. 30(A), 33(7)(B), 33(20)(B) INSITU
# Different cell positions due to INSITU-specific rows in Details sheet
# P&L has completely different cell positions (rows shifted down by 4)
# ────────────────────────────────────────────────────────────────────────────

_DETAILS_INSITU: list[CellMapping] = [
    CellMapping("Details", "P5", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "Q5", "dp_report.amenity_area_sqm", "float", 0),
    CellMapping("Details", "P8", "dp_report.setback_area_sqm", "float", 0),
    CellMapping("Details", "N19", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details", "R19", "dp_report.road_width_m|road_width_m", "float", 18.3),
    CellMapping("Details", "J22", "manual_inputs.protected_area_sqm", "float", 0),
    CellMapping("Details", "N22", "manual_inputs.old_setback_sqm", "float", 0),
    # NOC toggles
    CellMapping("Details", "R27", "manual_inputs.noc_highway", "int", 0),
    CellMapping("Details", "R28", "manual_inputs.noc_mmrda", "int", 0),
    CellMapping("Details", "R30", "manual_inputs.noc_railway", "int", 0),
    CellMapping("Details", "R31", "manual_inputs.noc_asi", "int", 0),
    CellMapping("Details", "R32", "manual_inputs.noc_mhcc", "int", 0),
    CellMapping("Details", "R33", "manual_inputs.noc_civil_aviation", "int", 0),
    CellMapping("Details", "R39", "dp_report.crz_zone", "bool_toggle", 0),
    CellMapping("Details", "R40", "manual_inputs.noc_other", "int", 0),
    CellMapping("Details", "G41", "manual_inputs.commercial_extra_multiplier", "float", 1.3),
    CellMapping("Details", "G48", "manual_inputs.residential_extra_multiplier", "float", 1.3),
    CellMapping("Details", "O49", "manual_inputs.plot_road_length_m", "float", 0),
    CellMapping("Details", "J56", "manual_inputs.sale_commercial_bua_sqm", "float", 15000),
    CellMapping("Details", "N60", "num_commercial", "int", 35),
    CellMapping("Details", "P60", "num_flats", "int", 146),
    CellMapping("Details", "O61", "manual_inputs.rent_commercial", "float", 150),
    CellMapping("Details", "Q61", "manual_inputs.rent_residential", "float", 70),
    CellMapping("Details", "O62", "manual_inputs.corpus_commercial", "float", 1000),
    CellMapping("Details", "Q62", "manual_inputs.corpus_residential", "float", 1000),
    CellMapping("Details", "O63", "manual_inputs.brokerage_commercial", "float", 25000),
    CellMapping("Details", "Q63", "manual_inputs.brokerage_residential", "float", 25000),
    CellMapping("Details", "O64", "manual_inputs.shifting_commercial", "float", 25000),
    CellMapping("Details", "Q64", "manual_inputs.shifting_residential", "float", 25000),
    CellMapping(
        "Details", "J66", "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm", "float", 58750
    ),
    CellMapping("Details", "O66", "manual_inputs.deposit_commercial", "float", 0),
    CellMapping("Details", "Q66", "manual_inputs.deposit_residential", "float", 0),
    CellMapping("Details", "O67", "manual_inputs.completion_months_commercial", "float", 24),
    CellMapping("Details", "Q67", "manual_inputs.completion_months_residential", "float", 46),
    CellMapping("Details", "N74", "manual_inputs.osd_ratio", "float", 0.35),
    CellMapping("Details", "N75", "manual_inputs.staircase_ratio", "float", 0.3),
    CellMapping("Details", "O76", "manual_inputs.construction_area_multiplier", "float", 1.5),
    CellMapping("Details", "N77", "manual_inputs.podium_ratio", "float", 0.7),
    CellMapping("Details", "O77", "manual_inputs.podium_floors", "int", 3),
    CellMapping("Details", "N78", "manual_inputs.basement_ratio", "float", 0.4),
    CellMapping("Details", "O78", "manual_inputs.basement_count", "int", 1),
]

_CONSTRUCTION_COST_INSITU: list[CellMapping] = [
    CellMapping("Construction Cost", "D8", "manual_inputs.const_rate_commercial", "float", 3600),
    CellMapping("Construction Cost", "D12", "manual_inputs.const_rate_residential", "float", 3600),
    CellMapping("Construction Cost", "D15", "manual_inputs.const_rate_podium", "float", 1700),
    CellMapping("Construction Cost", "F21", "manual_inputs.const_rate_basement", "float", 1700),
    CellMapping("Construction Cost", "F27", "manual_inputs.excavation_rate_brass", "float", 1350),
]

_MCGM_INSITU: list[CellMapping] = [
    CellMapping("MCGM PAYMENTS", "D5", "manual_inputs.scrutiny_rate_1", "float", 156),
    CellMapping("MCGM PAYMENTS", "D7", "manual_inputs.scrutiny_rate_2", "float", 156),
    CellMapping("MCGM PAYMENTS", "D9", "manual_inputs.scrutiny_rate_3", "float", 307),
    CellMapping("MCGM PAYMENTS", "J278", "manual_inputs.pco_rate", "float", 10),
]

_SUMMARY1_INSITU: list[CellMapping] = [
    CellMapping("SUMMARY 1", "D75", "manual_inputs.toggle_section_75", "int", 1),
    CellMapping("SUMMARY 1", "D77", "manual_inputs.toggle_section_77", "int", 1),
    CellMapping("SUMMARY 1", "D84", "manual_inputs.toggle_section_84", "int", 1),
    CellMapping("SUMMARY 1", "D86", "manual_inputs.toggle_section_86", "int", 1),
    CellMapping("SUMMARY 1", "I110", "manual_inputs.donations_misc", "float", 0),
    CellMapping("SUMMARY 1", "I112", "manual_inputs.special_approval_1", "float", 2500000),
    CellMapping("SUMMARY 1", "I113", "manual_inputs.special_approval_2", "float", 10000000),
]

# P&L for INSITU has COMPLETELY different cell positions (rows shifted)
_PNL_INSITU: list[CellMapping] = [
    CellMapping(
        "Profit & Loss Statement", "D23", "financial.sale_rate_commercial_gf", "float", 50000
    ),
    CellMapping(
        "Profit & Loss Statement", "D24", "financial.sale_rate_commercial_1f", "float", 35000
    ),
    CellMapping("Profit & Loss Statement", "C25", "manual_inputs.commercial_2f_area", "float", 0),
    CellMapping("Profit & Loss Statement", "D25", "financial.sale_rate_commercial_2f", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D26", "financial.sale_rate_commercial_other", "float", 30000
    ),
    CellMapping(
        "Profit & Loss Statement",
        "D36",
        "financial.sale_rate_residential|sale_rate_per_sqft",
        "float",
        25000,
    ),
    CellMapping(
        "Profit & Loss Statement", "C38", "manual_inputs.parking_units_for_sale", "int", 250
    ),
    CellMapping(
        "Profit & Loss Statement", "D38", "financial.parking_price_per_unit", "float", 1000000
    ),
]


# ────────────────────────────────────────────────────────────────────────────
# 33(20)(B) — FORCED TEMPLATE mapping for
#   "33 (20) B feasibility Clubbing  Format 10.04.2025.xlsx"
# Coordinates verified against the template's actual yellow input cells.
# Used whenever template_service._FORCED_TEMPLATE_NAME is set.
# ────────────────────────────────────────────────────────────────────────────

_DETAILS_FORCED: list[CellMapping] = [
    # ── Plot & Site Data ──────────────────────────────────────────────────
    CellMapping("Details", "P3", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "P6", "manual_inputs.plot_area_conveyance_sqm", "float", 0),
    CellMapping("Details", "P13", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "N16", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details", "R16", "dp_report.road_width_m|road_width_m", "float", 18.3),
    CellMapping("Details", "B18", "num_flats", "int", 0),
    CellMapping("Details", "N19", "manual_inputs.old_setback_sqm", "float", 0),
    # ── NOC Toggles (R24–R32) — 0=no, 1=yes ───────────────────────────────
    CellMapping("Details", "R24", "manual_inputs.noc_highway", "int", 0),
    CellMapping("Details", "R25", "manual_inputs.noc_mmrda", "int", 0),
    CellMapping("Details", "R26", "manual_inputs.noc_moef", "int", 0),
    CellMapping("Details", "R27", "manual_inputs.noc_railway", "int", 0),
    CellMapping("Details", "R28", "manual_inputs.noc_asi", "int", 0),
    CellMapping("Details", "R29", "manual_inputs.noc_mhcc", "int", 0),
    CellMapping("Details", "R30", "manual_inputs.noc_civil_aviation", "int", 0),
    CellMapping("Details", "R31", "dp_report.crz_zone", "bool_toggle", 0),
    CellMapping("Details", "R32", "manual_inputs.noc_other", "int", 0),
    # ── NOC Rates (Q24–Q32) — only set when override provided ─────────────
    CellMapping("Details", "Q24", "manual_inputs.noc_highway_rate", "float", 500000),
    CellMapping("Details", "Q25", "manual_inputs.noc_mmrda_rate", "float", 200000),
    CellMapping("Details", "Q26", "manual_inputs.noc_moef_rate", "float", 2500000),
    CellMapping("Details", "Q27", "manual_inputs.noc_railway_rate", "float", 500000),
    CellMapping("Details", "Q28", "manual_inputs.noc_asi_rate", "float", 500000),
    CellMapping("Details", "Q29", "manual_inputs.noc_mhcc_rate", "float", 100000),
    CellMapping("Details", "Q30", "manual_inputs.noc_civil_aviation_rate", "float", 1500000),
    CellMapping("Details", "Q31", "manual_inputs.noc_crz_rate", "float", 1000000),
    CellMapping("Details", "Q32", "manual_inputs.noc_other_rate", "float", 1500000),
    # ── BUA Multipliers ───────────────────────────────────────────────────
    CellMapping("Details", "G33", "manual_inputs.commercial_extra_multiplier", "float", 1.2),
    CellMapping("Details", "G38", "manual_inputs.residential_extra_multiplier", "float", 1.2),
    # ── Plot Frontage / RR Rate ───────────────────────────────────────────
    CellMapping("Details", "O39", "manual_inputs.plot_road_length_m", "float", 45),
    CellMapping(
        "Details",
        "Q39",
        "ready_reckoner.rr_residential_sqm|premium.rr_residential_sqm",
        "float",
        233720,
    ),
    # ── Sale Component ────────────────────────────────────────────────────
    CellMapping("Details", "J44", "manual_inputs.sale_commercial_mun_bua_sqm", "float", 350),
    # ── Existing Society Areas ────────────────────────────────────────────
    CellMapping("Details", "O46", "existing_commercial_carpet_sqft", "float", 660),
    CellMapping("Details", "Q46", "existing_residential_carpet_sqft", "float", 32440.5),
    CellMapping("Details", "N48", "num_commercial", "int", 3),
    CellMapping("Details", "P48", "num_flats", "int", 51),
    # ── Compensations (Rent, Corpus, Brokerage, Shifting) ─────────────────
    CellMapping("Details", "O49", "manual_inputs.rent_commercial", "float", 200),
    CellMapping("Details", "Q49", "manual_inputs.rent_residential", "float", 100),
    CellMapping("Details", "O50", "manual_inputs.corpus_commercial", "float", 1000),
    CellMapping("Details", "Q50", "manual_inputs.corpus_residential", "float", 1000),
    CellMapping("Details", "O51", "manual_inputs.brokerage_commercial", "float", 35000),
    CellMapping("Details", "O52", "manual_inputs.shifting_commercial", "float", 50000),
    CellMapping("Details", "Q52", "manual_inputs.shifting_residential", "float", 50000),
    # ── Ready Reckoner / Deposit / Completion Period ──────────────────────
    CellMapping(
        "Details",
        "J53",
        "ready_reckoner.rr_residential_sqm|premium.rr_residential_sqm",
        "float",
        128450,
    ),
    CellMapping("Details", "O53", "manual_inputs.deposit_commercial", "float", 0),
    CellMapping("Details", "Q53", "manual_inputs.deposit_residential", "float", 0),
    CellMapping("Details", "O54", "manual_inputs.completion_months_commercial", "float", 36),
    CellMapping("Details", "Q54", "manual_inputs.completion_months_residential", "float", 36),
    # ── Technical Ratios (N61–O65) ────────────────────────────────────────
    CellMapping("Details", "N61", "manual_inputs.osd_ratio", "float", 0.4),
    CellMapping("Details", "N62", "manual_inputs.staircase_ratio", "float", 0.25),
    CellMapping("Details", "O63", "manual_inputs.construction_area_multiplier", "float", 1.5),
    CellMapping("Details", "N64", "manual_inputs.podium_ratio", "float", 0.6),
    CellMapping("Details", "O64", "manual_inputs.podium_floors", "int", 1),
    CellMapping("Details", "N65", "manual_inputs.basement_ratio", "float", 0.6),
    CellMapping("Details", "O65", "manual_inputs.basement_count", "int", 2),
]

_MCGM_FORCED: list[CellMapping] = [
    # Road-width-dependent MCGM rates (above / below 24 m)
    CellMapping("MCGM PAYMENTS", "C233", "manual_inputs.mcgm_rate_above_24m", "float", 159),
    CellMapping("MCGM PAYMENTS", "C235", "manual_inputs.mcgm_rate_below_24m", "float", 80),
]

_STAMP_DUTY_FORCED: list[CellMapping] = [
    # Car parking units handed over to society
    CellMapping("STAMP DUTY", "B44", "manual_inputs.parking_given_to_society", "int", 54),
]

_SUMMARY1_FORCED: list[CellMapping] = [
    CellMapping("SUMMARY 1", "D75", "manual_inputs.toggle_section_75", "int", 1),
    CellMapping("SUMMARY 1", "D79", "manual_inputs.toggle_section_79", "int", 1),
    CellMapping("SUMMARY 1", "D81", "manual_inputs.toggle_section_81", "int", 1),
    CellMapping("SUMMARY 1", "D83", "manual_inputs.toggle_section_83", "int", 1),
    CellMapping("SUMMARY 1", "I102", "manual_inputs.cost_79a_acquisition", "float", 0),
    CellMapping("SUMMARY 1", "I105", "manual_inputs.donations_misc", "float", 500000),
    CellMapping("SUMMARY 1", "I107", "manual_inputs.special_approval_1", "float", 1500000),
    CellMapping("SUMMARY 1", "I108", "manual_inputs.special_approval_2", "float", 0),
]

_PNL_FORCED: list[CellMapping] = [
    CellMapping(
        "Profit & Loss Statement", "D19", "financial.sale_rate_commercial_gf", "float", 55000
    ),
    CellMapping("Profit & Loss Statement", "C20", "manual_inputs.commercial_1f_area", "float", 0),
    CellMapping("Profit & Loss Statement", "D20", "financial.sale_rate_commercial_1f", "float", 0),
    CellMapping("Profit & Loss Statement", "C21", "manual_inputs.commercial_2f_area", "float", 0),
    CellMapping("Profit & Loss Statement", "D21", "financial.sale_rate_commercial_2f", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D22", "financial.sale_rate_commercial_other", "float", 0
    ),
    CellMapping(
        "Profit & Loss Statement",
        "D28",
        "financial.sale_rate_residential|sale_rate_per_sqft",
        "float",
        38000,
    ),
    CellMapping(
        "Profit & Loss Statement", "C30", "manual_inputs.parking_units_for_sale", "int", 75
    ),
    CellMapping(
        "Profit & Loss Statement", "D30", "financial.parking_price_per_unit", "float", 1000000
    ),
]


# ────────────────────────────────────────────────────────────────────────────
# Legacy 33(20)(B) CLUBBING — kept for reference only; not active while forced
# ────────────────────────────────────────────────────────────────────────────

_DETAILS_2020B_CLUBBING: list[CellMapping] = [
    # ── Plot & Site Data ──────────────────────────────────────────────────
    CellMapping("Details", "P5", "mcgm_property.area_sqm|plot_area_sqm", "float", 1.0),
    CellMapping("Details", "Q5", "dp_report.amenity_area_sqm", "float", 0),
    CellMapping("Details", "P8", "dp_report.setback_area_sqm", "float", 0),
    CellMapping("Details", "P15", "mcgm_property.area_sqm|plot_area_sqm", "float", 1.0),
    CellMapping("Details", "N19", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details", "R19", "dp_report.road_width_m|road_width_m", "float", 18.3),
    # ── NOC Toggles ───────────────────────────────────────────────────────
    CellMapping("Details", "R27", "manual_inputs.noc_highway", "int", 0),
    CellMapping("Details", "R28", "manual_inputs.noc_mmrda", "int", 0),
    CellMapping("Details", "R30", "manual_inputs.noc_railway", "int", 0),
    CellMapping("Details", "R31", "manual_inputs.noc_asi", "int", 0),
    CellMapping("Details", "R32", "manual_inputs.noc_mhcc", "int", 0),
    CellMapping("Details", "R33", "manual_inputs.noc_civil_aviation", "int", 0),
    CellMapping("Details", "R34", "dp_report.crz_zone", "bool_toggle", 0),
    CellMapping("Details", "R35", "manual_inputs.noc_other", "int", 0),
    # ── Existing Areas & Multipliers ──────────────────────────────────────
    CellMapping("Details", "O35", "manual_inputs.existing_commercial_bua_sqm", "float", 490.52),
    CellMapping("Details", "G36", "manual_inputs.commercial_extra_multiplier", "float", 1.35),
    CellMapping("Details", "G43", "manual_inputs.residential_extra_multiplier", "float", 1.40),
    # ── RR Rates ──────────────────────────────────────────────────────────
    CellMapping(
        "Details",
        "P44",
        "ready_reckoner.rr_residential_sqm|premium.rr_residential_sqm",
        "float",
        427590,
    ),
    CellMapping(
        "Details",
        "Q44",
        "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm",
        "float",
        213130,
    ),
    CellMapping(
        "Details",
        "J61",
        "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm",
        "float",
        213130,
    ),
    # ── Society Details (Carpet & Counts) ─────────────────────────────────
    CellMapping("Details", "Q53", "existing_residential_carpet_sqft", "float", 21470),
    CellMapping("Details", "O53", "existing_commercial_carpet_sqft", "float", 0),
    CellMapping("Details", "P55", "num_flats", "int", 30),
    CellMapping("Details", "N55", "num_commercial", "int", 0),
    # ── Compensations (Rent, Corpus, Brokerage) ───────────────────────────
    CellMapping("Details", "O56", "manual_inputs.rent_commercial", "float", 150),
    CellMapping("Details", "Q56", "manual_inputs.rent_residential", "float", 100),
    CellMapping("Details", "O57", "manual_inputs.corpus_commercial", "float", 1500),
    CellMapping("Details", "Q57", "manual_inputs.corpus_residential", "float", 1000),
    CellMapping("Details", "O58", "manual_inputs.brokerage_commercial", "float", 100000),
    CellMapping("Details", "Q58", "manual_inputs.brokerage_residential", "float", 75000),
    CellMapping("Details", "O59", "manual_inputs.shifting_commercial", "float", 25000),
    CellMapping("Details", "Q59", "manual_inputs.shifting_residential", "float", 25000),
    # ── Financials (Sale Rate & Deposit) ──────────────────────────────────
    CellMapping(
        "Details", "P61", "financial.sale_rate_residential|sale_rate_per_sqft", "float", 65000
    ),
    CellMapping("Details", "O61", "manual_inputs.deposit_commercial", "float", 0),
    CellMapping("Details", "Q61", "manual_inputs.deposit_residential", "float", 0),
    # ── Completion Period ─────────────────────────────────────────────────
    CellMapping("Details", "O62", "manual_inputs.completion_months_commercial", "float", 24),
    CellMapping("Details", "Q62", "manual_inputs.completion_months_residential", "float", 46),
    # ── Technical Ratios ──────────────────────────────────────────────────
    CellMapping("Details", "N69", "manual_inputs.osd_ratio", "float", 0.35),
    CellMapping("Details", "N70", "manual_inputs.staircase_ratio", "float", 0.35),
    CellMapping("Details", "O71", "manual_inputs.construction_area_multiplier", "float", 1.5),
    CellMapping("Details", "N72", "manual_inputs.podium_ratio", "float", 0.6),
    CellMapping("Details", "O72", "manual_inputs.podium_floors", "int", 5),
    CellMapping("Details", "N73", "manual_inputs.basement_ratio", "float", 0.4),
    CellMapping("Details", "O73", "manual_inputs.basement_count", "int", 1),
]


# ────────────────────────────────────────────────────────────────────────────
# 33(20)(B) INSITU — shifted cells from 33(20)(B) CLUBBING
# Details has extra INSITU rows causing shifts
# ────────────────────────────────────────────────────────────────────────────

_DETAILS_2020B_INSITU: list[CellMapping] = [
    CellMapping("Details", "P5", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "Q5", "dp_report.amenity_area_sqm", "float", 0),
    CellMapping("Details", "P8", "dp_report.setback_area_sqm", "float", 0),
    CellMapping("Details", "P15", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "N19", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details", "R19", "dp_report.road_width_m|road_width_m", "float", 18.3),
    CellMapping("Details", "J22", "manual_inputs.protected_area_sqm", "float", 0),
    CellMapping("Details", "N22", "manual_inputs.old_setback_sqm", "float", 0),
    # NOC toggles
    CellMapping("Details", "R27", "manual_inputs.noc_highway", "int", 0),
    CellMapping("Details", "R28", "manual_inputs.noc_mmrda", "int", 0),
    CellMapping("Details", "R30", "manual_inputs.noc_railway", "int", 0),
    CellMapping("Details", "R31", "manual_inputs.noc_asi", "int", 0),
    CellMapping("Details", "R32", "manual_inputs.noc_mhcc", "int", 0),
    CellMapping("Details", "R33", "manual_inputs.noc_civil_aviation", "int", 0),
    CellMapping("Details", "R38", "dp_report.crz_zone", "bool_toggle", 0),
    CellMapping("Details", "R39", "manual_inputs.noc_other", "int", 0),
    CellMapping("Details", "O39", "manual_inputs.existing_commercial_bua_sqm", "float", 490.52),
    CellMapping("Details", "G40", "manual_inputs.commercial_extra_multiplier", "float", 1.35),
    CellMapping("Details", "G47", "manual_inputs.residential_extra_multiplier", "float", 1.4),
    CellMapping("Details", "O48", "manual_inputs.plot_road_length_m", "float", 0),
    CellMapping("Details", "J55", "manual_inputs.sale_commercial_bua_sqm", "float", 2500),
    CellMapping("Details", "O57", "existing_commercial_carpet_sqft", "float", 4800),
    CellMapping("Details", "Q57", "existing_residential_carpet_sqft", "float", 69300),
    CellMapping("Details", "N59", "num_commercial", "int", 12),
    CellMapping("Details", "P59", "num_flats", "int", 138),
    CellMapping("Details", "O60", "manual_inputs.rent_commercial", "float", 350),
    CellMapping("Details", "Q60", "manual_inputs.rent_residential", "float", 150),
    CellMapping("Details", "O61", "manual_inputs.corpus_commercial", "float", 1000),
    CellMapping("Details", "Q61", "manual_inputs.corpus_residential", "float", 1000),
    CellMapping("Details", "O62", "manual_inputs.brokerage_commercial", "float", 100000),
    CellMapping("Details", "Q62", "manual_inputs.brokerage_residential", "float", 75000),
    CellMapping("Details", "O63", "manual_inputs.shifting_commercial", "float", 25000),
    CellMapping("Details", "Q63", "manual_inputs.shifting_residential", "float", 25000),
    CellMapping(
        "Details", "J65", "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm", "float", 75910
    ),
    CellMapping("Details", "O65", "manual_inputs.deposit_commercial", "float", 0),
    CellMapping("Details", "Q65", "manual_inputs.deposit_residential", "float", 0),
    CellMapping("Details", "O66", "manual_inputs.completion_months_commercial", "float", 18),
    CellMapping("Details", "Q66", "manual_inputs.completion_months_residential", "float", 46),
    CellMapping("Details", "N73", "manual_inputs.osd_ratio", "float", 0.35),
    CellMapping("Details", "N74", "manual_inputs.staircase_ratio", "float", 0.35),
    CellMapping("Details", "O75", "manual_inputs.construction_area_multiplier", "float", 1.5),
    CellMapping("Details", "N76", "manual_inputs.podium_ratio", "float", 0.6),
    CellMapping("Details", "O76", "manual_inputs.podium_floors", "int", 5),
    CellMapping("Details", "N77", "manual_inputs.basement_ratio", "float", 0.4),
    CellMapping("Details", "O77", "manual_inputs.basement_count", "int", 2),
]

_MCGM_2020B_INSITU: list[CellMapping] = [
    CellMapping("MCGM PAYMENTS", "D5", "manual_inputs.scrutiny_rate_1", "float", 156),
    CellMapping("MCGM PAYMENTS", "D7", "manual_inputs.scrutiny_rate_2", "float", 156),
    CellMapping("MCGM PAYMENTS", "D9", "manual_inputs.scrutiny_rate_3", "float", 307),
    CellMapping("MCGM PAYMENTS", "C214", "manual_inputs.slum_tdr_rate", "float", 0.9),
    CellMapping("MCGM PAYMENTS", "C219", "manual_inputs.gen_tdr_rate", "float", 0.65),
    CellMapping("MCGM PAYMENTS", "J274", "manual_inputs.tree_noc_rate", "float", 10),
]

_SUMMARY1_2020B_INSITU: list[CellMapping] = [
    CellMapping("SUMMARY 1", "D75", "manual_inputs.toggle_section_75", "int", 1),
    CellMapping("SUMMARY 1", "D77", "manual_inputs.toggle_section_77", "int", 1),
    CellMapping("SUMMARY 1", "D84", "manual_inputs.toggle_section_84", "int", 1),
    CellMapping("SUMMARY 1", "D86", "manual_inputs.toggle_section_86", "int", 1),
    CellMapping("SUMMARY 1", "I106", "manual_inputs.estate_noc_premium", "float", 0),
    CellMapping("SUMMARY 1", "I109", "manual_inputs.donations_misc", "float", 500000),
    CellMapping("SUMMARY 1", "I111", "manual_inputs.special_approval_1", "float", 2500000),
    CellMapping("SUMMARY 1", "I112", "manual_inputs.special_approval_2", "float", 20000000),
]


# ────────────────────────────────────────────────────────────────────────────
# 33(12)(B) ONLY — Reg. 30(A), 33(7)(B), 33(12)B (without 33(20)(B))
# Different row offsets: reservation at N18, road width at R18, etc.
# ────────────────────────────────────────────────────────────────────────────

_DETAILS_33_12B_ONLY: list[CellMapping] = [
    CellMapping("Details", "P5", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "Q5", "dp_report.amenity_area_sqm", "float", 0),
    CellMapping("Details", "P8", "dp_report.setback_area_sqm", "float", 0),
    CellMapping("Details", "P17", "manual_inputs.additional_plot_area_sqm", "float", 0),
    CellMapping("Details", "N18", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details", "R18", "dp_report.road_width_m|road_width_m", "float", 9),
    CellMapping("Details", "N21", "manual_inputs.old_setback_sqm", "float", 0),
    # NOC toggles at R26–R34
    CellMapping("Details", "R26", "manual_inputs.noc_highway", "int", 0),
    CellMapping("Details", "R27", "manual_inputs.noc_mmrda", "int", 0),
    CellMapping("Details", "R29", "manual_inputs.noc_railway", "int", 0),
    CellMapping("Details", "R30", "manual_inputs.noc_asi", "int", 0),
    CellMapping("Details", "R31", "manual_inputs.noc_mhcc", "int", 0),
    CellMapping("Details", "R32", "manual_inputs.noc_civil_aviation", "int", 0),
    CellMapping("Details", "R33", "dp_report.crz_zone", "bool_toggle", 0),
    CellMapping("Details", "R34", "manual_inputs.noc_other", "int", 0),
    CellMapping("Details", "G35", "manual_inputs.commercial_extra_multiplier", "float", 1),
    CellMapping("Details", "G40", "manual_inputs.residential_extra_multiplier", "float", 1.22),
    CellMapping("Details", "O41", "manual_inputs.plot_road_length_m", "float", 0),
    CellMapping("Details", "J46", "manual_inputs.sale_commercial_bua_sqm", "float", 0),
    CellMapping("Details", "O48", "existing_commercial_carpet_sqft", "float", 0),
    CellMapping("Details", "Q48", "existing_residential_carpet_sqft", "float", 15726.28),
    CellMapping("Details", "N50", "num_commercial", "int", 0),
    CellMapping("Details", "P50", "num_flats", "int", 21),
    CellMapping("Details", "O51", "manual_inputs.rent_commercial", "float", 0),
    CellMapping("Details", "Q51", "manual_inputs.rent_residential", "float", 70),
    CellMapping("Details", "O52", "manual_inputs.corpus_commercial", "float", 0),
    CellMapping("Details", "Q52", "manual_inputs.corpus_residential", "float", 0),
    CellMapping("Details", "O53", "manual_inputs.brokerage_commercial", "float", 0),
    CellMapping("Details", "Q53", "manual_inputs.brokerage_residential", "float", 25000),
    CellMapping("Details", "O54", "manual_inputs.shifting_commercial", "float", 0),
    CellMapping("Details", "Q54", "manual_inputs.shifting_residential", "float", 25000),
    CellMapping(
        "Details", "J55", "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm", "float", 76180
    ),
    CellMapping("Details", "O55", "manual_inputs.deposit_commercial", "float", 0),
    CellMapping("Details", "Q55", "manual_inputs.deposit_residential", "float", 0),
    CellMapping("Details", "O56", "manual_inputs.completion_months_commercial", "float", 0),
    CellMapping("Details", "Q56", "manual_inputs.completion_months_residential", "float", 36),
    CellMapping("Details", "N63", "manual_inputs.osd_ratio", "float", 0.4),
    CellMapping("Details", "N64", "manual_inputs.staircase_ratio", "float", 0.25),
    CellMapping("Details", "O65", "manual_inputs.construction_area_multiplier", "float", 1.3),
    CellMapping("Details", "N66", "manual_inputs.podium_ratio", "float", 0.6),
    CellMapping("Details", "O66", "manual_inputs.podium_floors", "int", 0),
    CellMapping("Details", "N67", "manual_inputs.basement_ratio", "float", 0.4),
    CellMapping("Details", "O67", "manual_inputs.basement_count", "int", 1),
]

_CONSTRUCTION_COST_33_12B_ONLY: list[CellMapping] = [
    CellMapping("Construction Cost", "D8", "manual_inputs.const_rate_commercial", "float", 3800),
    CellMapping("Construction Cost", "D12", "manual_inputs.const_rate_residential", "float", 4000),
    CellMapping("Construction Cost", "D15", "manual_inputs.const_rate_podium", "float", 1800),
    CellMapping("Construction Cost", "F21", "manual_inputs.const_rate_basement", "float", 2000),
    CellMapping("Construction Cost", "F27", "manual_inputs.excavation_rate_brass", "float", 1350),
]

_MCGM_33_12B_ONLY: list[CellMapping] = [
    CellMapping("MCGM PAYMENTS", "D5", "manual_inputs.scrutiny_rate_1", "float", 156),
    CellMapping("MCGM PAYMENTS", "D7", "manual_inputs.scrutiny_rate_2", "float", 156),
    CellMapping("MCGM PAYMENTS", "D9", "manual_inputs.scrutiny_rate_3", "float", 307),
    CellMapping("MCGM PAYMENTS", "C213", "manual_inputs.slum_tdr_rate", "float", 0.9),
    CellMapping("MCGM PAYMENTS", "C218", "manual_inputs.gen_tdr_rate", "float", 0.65),
    CellMapping("MCGM PAYMENTS", "J268", "manual_inputs.pco_rate", "float", 10),
]

# Summary 1 in this template has toggle cells at D74/D76/D83/D85 (not D75/D77/D84/D86)
_SUMMARY1_33_12B_ONLY: list[CellMapping] = [
    CellMapping("SUMMARY 1", "D74", "manual_inputs.toggle_section_75", "int", 1),
    CellMapping("SUMMARY 1", "D76", "manual_inputs.toggle_section_77", "int", 1),
    CellMapping("SUMMARY 1", "D83", "manual_inputs.toggle_section_84", "int", 1),
    CellMapping("SUMMARY 1", "D85", "manual_inputs.toggle_section_86", "int", 1),
    CellMapping("SUMMARY 1", "I100", "manual_inputs.estate_noc_premium", "float", 0),
    CellMapping("SUMMARY 1", "I103", "manual_inputs.estate_lease_premium", "float", 0),
    CellMapping("SUMMARY 1", "I105", "manual_inputs.special_approval_1", "float", 0),
    CellMapping("SUMMARY 1", "I106", "manual_inputs.special_approval_2", "float", 0),
]

_PNL_33_12B_ONLY: list[CellMapping] = [
    CellMapping("Profit & Loss Statement", "C19", "manual_inputs.commercial_gf_area", "float", 0),
    CellMapping("Profit & Loss Statement", "D19", "financial.sale_rate_commercial_gf", "float", 0),
    CellMapping("Profit & Loss Statement", "C20", "manual_inputs.commercial_1f_area", "float", 0),
    CellMapping("Profit & Loss Statement", "D20", "financial.sale_rate_commercial_1f", "float", 0),
    CellMapping("Profit & Loss Statement", "C21", "manual_inputs.commercial_2f_area", "float", 0),
    CellMapping("Profit & Loss Statement", "D21", "financial.sale_rate_commercial_2f", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D22", "financial.sale_rate_commercial_other", "float", 0
    ),
    CellMapping(
        "Profit & Loss Statement",
        "D28",
        "financial.sale_rate_residential|sale_rate_per_sqft",
        "float",
        37000,
    ),
    CellMapping(
        "Profit & Loss Statement", "C30", "manual_inputs.parking_units_for_sale", "int", 50
    ),
    CellMapping(
        "Profit & Loss Statement", "D30", "financial.parking_price_per_unit", "float", 1000000
    ),
]


# ────────────────────────────────────────────────────────────────────────────
# 33(19) — 100% Feasibility Format
# Different cell positions from all other templates (e.g., P4 not P5)
# ────────────────────────────────────────────────────────────────────────────

_DETAILS_33_19: list[CellMapping] = [
    CellMapping("Details", "P4", "mcgm_property.area_sqm|plot_area_sqm", "float"),
    CellMapping("Details", "P7", "dp_report.setback_area_sqm", "float", 0),
    CellMapping("Details", "N17", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details", "R17", "dp_report.road_width_m|road_width_m", "float", 36),
    # NOC toggles at R26–R34
    CellMapping("Details", "R26", "manual_inputs.noc_highway", "int", 0),
    CellMapping("Details", "R27", "manual_inputs.noc_mmrda", "int", 0),
    CellMapping("Details", "R29", "manual_inputs.noc_railway", "int", 0),
    CellMapping("Details", "R30", "manual_inputs.noc_asi", "int", 0),
    CellMapping("Details", "R31", "manual_inputs.noc_mhcc", "int", 0),
    CellMapping("Details", "R32", "manual_inputs.noc_civil_aviation", "int", 0),
    CellMapping("Details", "R33", "dp_report.crz_zone", "bool_toggle", 0),
    CellMapping("Details", "R34", "manual_inputs.noc_other", "int", 0),
    CellMapping("Details", "O33", "manual_inputs.existing_commercial_bua_sqm", "float", 0),
    CellMapping("Details", "G35", "manual_inputs.commercial_extra_multiplier", "float", 1.36),
    CellMapping("Details", "G40", "manual_inputs.residential_extra_multiplier", "float", 1),
    CellMapping("Details", "O41", "manual_inputs.plot_road_length_m", "float", 50),
    CellMapping("Details", "O48", "existing_commercial_carpet_sqft", "float", 29428.03),
    CellMapping("Details", "Q48", "existing_residential_carpet_sqft", "float", 0),
    CellMapping("Details", "N50", "num_commercial", "int", 81),
    CellMapping("Details", "P50", "num_flats", "int", 0),
    CellMapping("Details", "O51", "manual_inputs.rent_commercial", "float", 180),
    CellMapping("Details", "Q51", "manual_inputs.rent_residential", "float", 0),
    CellMapping("Details", "O52", "manual_inputs.corpus_commercial", "float", 2000),
    CellMapping("Details", "Q52", "manual_inputs.corpus_residential", "float", 0),
    CellMapping("Details", "O53", "manual_inputs.brokerage_commercial", "float", 50000),
    CellMapping("Details", "Q53", "manual_inputs.brokerage_residential", "float", 0),
    CellMapping("Details", "O54", "manual_inputs.shifting_commercial", "float", 25000),
    CellMapping("Details", "Q54", "manual_inputs.shifting_residential", "float", 0),
    CellMapping(
        "Details", "J55", "ready_reckoner.rr_open_land_sqm|premium.rr_open_land_sqm", "float", 61580
    ),
    CellMapping("Details", "O55", "manual_inputs.deposit_commercial", "float", 0),
    CellMapping("Details", "Q55", "manual_inputs.deposit_residential", "float", 0),
    CellMapping("Details", "O56", "manual_inputs.completion_months_commercial", "float", 36),
    CellMapping("Details", "Q56", "manual_inputs.completion_months_residential", "float", 0),
    CellMapping("Details", "H63", "manual_inputs.osd_ratio", "float", 0.3),
    CellMapping("Details", "J63", "manual_inputs.osd_ratio_2", "float", 0.7),
    CellMapping("Details", "N63", "manual_inputs.staircase_ratio", "float", 0.35),
    CellMapping("Details", "N64", "manual_inputs.staircase_ratio_2", "float", 0.25),
    CellMapping("Details", "O65", "manual_inputs.construction_area_multiplier", "float", 1.5),
    CellMapping("Details", "N66", "manual_inputs.podium_ratio", "float", 0.75),
    CellMapping("Details", "O66", "manual_inputs.podium_floors", "int", 3),
    CellMapping("Details", "N67", "manual_inputs.basement_ratio", "float", 0.4),
    CellMapping("Details", "O67", "manual_inputs.basement_count", "int", 1),
]

_CONSTRUCTION_COST_33_19: list[CellMapping] = [
    CellMapping("Construction Cost", "D8", "manual_inputs.const_rate_commercial", "float", 3800),
    CellMapping("Construction Cost", "D12", "manual_inputs.const_rate_residential", "float", 3800),
    CellMapping("Construction Cost", "D15", "manual_inputs.const_rate_podium", "float", 1800),
    CellMapping("Construction Cost", "H21", "manual_inputs.const_rate_basement", "float", 2000),
    CellMapping("Construction Cost", "F27", "manual_inputs.excavation_rate_brass", "float", 1350),
]

_MCGM_33_19: list[CellMapping] = [
    CellMapping("MCGM PAYMENTS", "D5", "manual_inputs.scrutiny_rate_1", "float", 307),
    CellMapping("MCGM PAYMENTS", "D7", "manual_inputs.scrutiny_rate_2", "float", 307),
    CellMapping("MCGM PAYMENTS", "D9", "manual_inputs.scrutiny_rate_3", "float", 307),
    CellMapping("MCGM PAYMENTS", "J271", "manual_inputs.pco_rate", "float", 25),
]

_SUMMARY1_33_19: list[CellMapping] = [
    CellMapping("SUMMARY 1", "D75", "manual_inputs.toggle_section_75", "int", 1),
    CellMapping("SUMMARY 1", "D77", "manual_inputs.toggle_section_77", "int", 1),
    CellMapping("SUMMARY 1", "D84", "manual_inputs.toggle_section_84", "int", 1),
    CellMapping("SUMMARY 1", "D86", "manual_inputs.toggle_section_86", "int", 1),
    CellMapping("SUMMARY 1", "I87", "manual_inputs.land_acquisition_cost", "float", 190000000),
    CellMapping("SUMMARY 1", "I109", "manual_inputs.donations_misc", "float", 0),
    CellMapping("SUMMARY 1", "I112", "manual_inputs.special_approval_1", "float", 0),
    CellMapping("SUMMARY 1", "I114", "manual_inputs.special_approval_1", "float", 2500000),
    CellMapping("SUMMARY 1", "I115", "manual_inputs.special_approval_2", "float", 20000000),
]

_PNL_33_19: list[CellMapping] = [
    CellMapping("Profit & Loss Statement", "C21", "manual_inputs.commercial_gf_area", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D21", "financial.sale_rate_commercial_gf", "float", 70000
    ),
    CellMapping("Profit & Loss Statement", "C22", "manual_inputs.commercial_1f_area", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D22", "financial.sale_rate_commercial_1f", "float", 45000
    ),
    CellMapping(
        "Profit & Loss Statement", "D23", "financial.sale_rate_commercial_other", "float", 30000
    ),
    CellMapping(
        "Profit & Loss Statement",
        "D29",
        "financial.sale_rate_residential|sale_rate_per_sqft",
        "float",
        24000,
    ),
    CellMapping(
        "Profit & Loss Statement", "C31", "manual_inputs.parking_units_for_sale", "int", 100
    ),
    CellMapping(
        "Profit & Loss Statement", "D31", "financial.parking_price_per_unit", "float", 1000000
    ),
]


# ────────────────────────────────────────────────────────────────────────────
# 33(9) — Only Residential (completely different sheet structure)
# Uses "Details to be filled" instead of "Details", "Summary" instead
# of "SUMMARY 1", different Construction Cost cell layout
# ────────────────────────────────────────────────────────────────────────────

_DETAILS_33_9: list[CellMapping] = [
    # B3 is a formula (=16920+5206.9), B4 is also formula — skip
    CellMapping("Details to be filled", "C4", "dp_report.amenity_area_sqm", "float", 0),
    CellMapping("Details to be filled", "B5", "manual_inputs.osd_ratio", "float", 0.6),
    CellMapping("Details to be filled", "G5", "dp_report.reservation_area_sqm", "float", 0),
    CellMapping("Details to be filled", "B6", "manual_inputs.rent_residential", "float", 80),
    CellMapping("Details to be filled", "C6", "manual_inputs.rent_commercial", "float", 0),
    CellMapping("Details to be filled", "B7", "manual_inputs.corpus_residential", "float", 900),
    CellMapping("Details to be filled", "C7", "manual_inputs.corpus_commercial", "float", 0),
    CellMapping(
        "Details to be filled", "B8", "manual_inputs.brokerage_residential", "float", 45000
    ),
    CellMapping("Details to be filled", "C8", "manual_inputs.brokerage_commercial", "float", 0),
    CellMapping("Details to be filled", "B9", "manual_inputs.shifting_residential", "float", 45000),
    CellMapping("Details to be filled", "C9", "manual_inputs.shifting_commercial", "float", 0),
    CellMapping(
        "Details to be filled", "B10", "manual_inputs.completion_months_residential", "float", 72
    ),
    CellMapping(
        "Details to be filled", "C10", "manual_inputs.completion_months_commercial", "float", 0
    ),
    CellMapping("Details to be filled", "G10", "manual_inputs.plot_road_length_m", "float", 100),
    # NOC toggles — H column (different from other templates)
    CellMapping("Details to be filled", "H27", "manual_inputs.noc_highway", "int", 0),
    CellMapping("Details to be filled", "H28", "manual_inputs.noc_mmrda", "int", 0),
    CellMapping("Details to be filled", "H29", "manual_inputs.noc_fire", "int", 1),
    CellMapping("Details to be filled", "H30", "manual_inputs.noc_railway", "int", 1),
    CellMapping("Details to be filled", "H31", "manual_inputs.noc_asi", "int", 0),
    CellMapping("Details to be filled", "H32", "manual_inputs.noc_mhcc", "int", 0),
    CellMapping("Details to be filled", "H33", "dp_report.crz_zone", "bool_toggle", 1),
    CellMapping("Details to be filled", "H34", "manual_inputs.noc_civil_aviation", "int", 0),
    CellMapping("Details to be filled", "H35", "manual_inputs.noc_other", "int", 1),
    # Technical ratios
    CellMapping("Details to be filled", "B45", "manual_inputs.staircase_ratio", "float", 0.25),
    CellMapping(
        "Details to be filled", "B46", "manual_inputs.construction_area_multiplier", "float", 1.2
    ),
    CellMapping("Details to be filled", "B47", "manual_inputs.podium_ratio", "float", 0.55),
    CellMapping("Details to be filled", "B48", "manual_inputs.basement_ratio_1", "float", 0.45),
    CellMapping("Details to be filled", "B51", "manual_inputs.osd_extra", "float", 0.1),
    CellMapping("Details to be filled", "B52", "manual_inputs.staircase_ratio_2", "float", 0.2),
    CellMapping(
        "Details to be filled", "C53", "manual_inputs.construction_area_multiplier_2", "float", 1.5
    ),
    CellMapping("Details to be filled", "B54", "manual_inputs.podium_ratio_2", "float", 0.6),
    CellMapping("Details to be filled", "C54", "manual_inputs.podium_floors", "int", 3),
    CellMapping("Details to be filled", "B55", "manual_inputs.basement_ratio", "float", 0.4),
    CellMapping("Details to be filled", "C55", "manual_inputs.basement_count", "int", 1),
]

_CONSTRUCTION_COST_33_9: list[CellMapping] = [
    CellMapping("Construction Cost", "D8", "manual_inputs.const_rate_commercial", "float", 3500),
    CellMapping("Construction Cost", "D13", "manual_inputs.const_rate_residential", "float", 3500),
    CellMapping("Construction Cost", "D18", "manual_inputs.const_rate_podium", "float", 2800),
    CellMapping(
        "Construction Cost", "D22", "manual_inputs.const_rate_podium_parking", "float", 1700
    ),
    CellMapping("Construction Cost", "H28", "manual_inputs.const_rate_basement", "float", 2000),
    CellMapping("Construction Cost", "F34", "manual_inputs.excavation_rate_brass", "float", 1350),
]

_MCGM_33_9: list[CellMapping] = [
    CellMapping("MCGM PAYMENTS", "D5", "manual_inputs.scrutiny_rate_1", "float", 210),
    CellMapping("MCGM PAYMENTS", "D7", "manual_inputs.scrutiny_rate_2", "float", 210),
    CellMapping("MCGM PAYMENTS", "D9", "manual_inputs.scrutiny_rate_3", "float", 350),
    CellMapping("MCGM PAYMENTS", "D112", "manual_inputs.tdr_rate", "float", 1.3),
]

# 33(9) uses "Summary" sheet (not "SUMMARY 1"), different toggle rows
_SUMMARY_33_9: list[CellMapping] = [
    CellMapping("Summary", "D65", "manual_inputs.toggle_section_75", "int", 2),
    CellMapping("Summary", "D69", "manual_inputs.toggle_section_77", "int", 2),
    CellMapping("Summary", "D71", "manual_inputs.toggle_section_84", "int", 2),
    CellMapping("Summary", "D73", "manual_inputs.toggle_section_86", "int", 1),
    CellMapping("Summary", "I87", "manual_inputs.land_acquisition_cost", "float", 1000000000),
    CellMapping("Summary", "I90", "manual_inputs.donations_misc", "float", 5000000),
    CellMapping("Summary", "I92", "manual_inputs.special_approval_1", "float", 1500000),
    CellMapping("Summary", "I93", "manual_inputs.special_approval_2", "float", 40000000),
]

_PNL_33_9: list[CellMapping] = [
    CellMapping("Profit & Loss Statement", "C19", "manual_inputs.commercial_gf_area", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D19", "financial.sale_rate_commercial_gf", "float", 150000
    ),
    CellMapping("Profit & Loss Statement", "C20", "manual_inputs.commercial_1f_area", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D20", "financial.sale_rate_commercial_1f", "float", 80000
    ),
    CellMapping("Profit & Loss Statement", "C21", "manual_inputs.commercial_2f_area", "float", 0),
    CellMapping(
        "Profit & Loss Statement", "D21", "financial.sale_rate_commercial_2f", "float", 40000
    ),
    CellMapping(
        "Profit & Loss Statement", "D22", "financial.sale_rate_commercial_other", "float", 28000
    ),
    CellMapping(
        "Profit & Loss Statement", "C30", "manual_inputs.parking_units_for_sale", "int", 400
    ),
]


# ── Assemble per-scheme mapping dicts ─────────────────────────────────────

CELL_MAPPINGS: dict[str, list[CellMapping]] = {
    # ── Original CLUBBING schemes (unchanged) ─────────────────────────
    "33(7)(B)": (
        _DETAILS_COMMON + _CONSTRUCTION_COST_COMMON + _MCGM_COMMON + _SUMMARY1_COMMON + _PNL_COMMON
    ),
    "30(A)": (
        _DETAILS_COMMON + _CONSTRUCTION_COST_COMMON + _MCGM_COMMON + _SUMMARY1_COMMON + _PNL_COMMON
    ),
    "33(20)(B)": (
        _DETAILS_FORCED + _MCGM_FORCED + _STAMP_DUTY_FORCED + _SUMMARY1_FORCED + _PNL_FORCED
    ),
    # ── New CLUBBING schemes ──────────────────────────────────────────
    "33(12)(B)": (
        _DETAILS_33_12B + _CONSTRUCTION_COST_33_12B + _MCGM_33_12B + _SUMMARY1_33_12B + _PNL_33_12B
    ),
    "33(7)(A)": (
        _DETAILS_33_7A + _CONSTRUCTION_COST_33_7A + _MCGM_33_7A + _SUMMARY1_33_7A + _PNL_33_7A
    ),
    "33(12)(B)_ONLY": (
        _DETAILS_33_12B_ONLY
        + _CONSTRUCTION_COST_33_12B_ONLY
        + _MCGM_33_12B_ONLY
        + _SUMMARY1_33_12B_ONLY
        + _PNL_33_12B_ONLY
    ),
    # ── INSITU schemes ────────────────────────────────────────────────
    "30(A)_INSITU": (
        _DETAILS_INSITU + _CONSTRUCTION_COST_INSITU + _MCGM_INSITU + _SUMMARY1_INSITU + _PNL_INSITU
    ),
    "33(7)(B)_INSITU": (
        _DETAILS_INSITU + _CONSTRUCTION_COST_INSITU + _MCGM_INSITU + _SUMMARY1_INSITU + _PNL_INSITU
    ),
    "33(20)(B)_INSITU": (
        _DETAILS_2020B_INSITU
        + _CONSTRUCTION_COST_COMMON
        + _MCGM_2020B_INSITU
        + _SUMMARY1_2020B_INSITU
        + _PNL_COMMON
    ),
    # ── Standalone schemes ────────────────────────────────────────────
    "33(19)": (
        _DETAILS_33_19 + _CONSTRUCTION_COST_33_19 + _MCGM_33_19 + _SUMMARY1_33_19 + _PNL_33_19
    ),
    "33(9)": (_DETAILS_33_9 + _CONSTRUCTION_COST_33_9 + _MCGM_33_9 + _SUMMARY_33_9 + _PNL_33_9),
}


class CellMapper:
    """Maps microservice data to yellow cells in templates."""

    def __init__(self):
        self.mappings = CELL_MAPPINGS

    def get_mappings_for_scheme(self, scheme: str) -> list[CellMapping]:
        if scheme in self.mappings:
            return self.mappings[scheme]
        for key in self.mappings:
            if scheme in key or key in scheme:
                return self.mappings[key]
        return self.mappings.get("33(7)(B)", [])

    def map_data_to_cells(self, scheme: str, all_data: dict[str, Any]) -> dict[str, Any]:
        """Map all microservice data to cell values.

        Returns dict of ``"Sheet!Cell" -> value`` for every yellow cell that
        can be resolved.  Formula cells are skipped automatically.

        Keys use composite ``"SheetName!CellCoord"`` format to avoid
        collisions when different sheets share the same cell coordinate
        (e.g. ``Construction Cost!F21`` vs ``MCGM PAYMENTS!F21``).
        """
        mappings = self.get_mappings_for_scheme(scheme)
        cell_values: dict[str, Any] = {}

        for mapping in mappings:
            if mapping.is_formula:
                continue

            value = self._resolve_path(all_data, mapping.data_path)

            # Fall back to default if path didn't resolve
            if value is None:
                value = "Data Unavailable" if mapping.transform == "str" else mapping.default

            if value is None:
                continue

            # Transform
            try:
                if mapping.transform == "float":
                    value = float(value)
                elif mapping.transform == "int":
                    value = int(float(value))
                elif mapping.transform == "str":
                    value = str(value)
                elif mapping.transform == "bool_toggle":
                    value = 1 if value else 0
            except (ValueError, TypeError):
                value = mapping.default
                if value is None:
                    continue

            key = f"{mapping.sheet}!{mapping.cell}"
            cell_values[key] = value
            logger.debug("Mapped %s → %s = %s", mapping.data_path, key, value)

        return cell_values

    # ── helpers ────────────────────────────────────────────────────────────

    def _resolve_path(self, data: dict, path_expr: str) -> Any:
        """Resolve a data path with ``|`` fallback support.

        ``"mcgm_property.area_sqm|plot_area_sqm"``
        → try ``data["mcgm_property"]["area_sqm"]`` first,
          then ``data["plot_area_sqm"]``.
        """
        for path in path_expr.split("|"):
            val = self._get_nested_value(data, path.strip())
            if val is not None:
                return val
        return None

    @staticmethod
    def _get_nested_value(data: dict, path: str) -> Any:
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value


# Singleton
cell_mapper = CellMapper()
