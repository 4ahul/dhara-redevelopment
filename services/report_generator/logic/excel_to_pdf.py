"""
Excel to PDF converter service.
Uses the existing pdf_builder to create a proper formatted PDF,
then optionally appends the Excel sheets as attachments.
"""

import logging
from pathlib import Path
from io import BytesIO
from typing import Optional, Tuple
from datetime import datetime
import os
import sys

service_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(service_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)

logger = logging.getLogger(__name__)


def generate_report_with_pdf(
    scheme: str,
    all_data: dict,
    output_dir: Path,
    society_name: str,
    redevelopment_type: str = "CLUBBING",
) -> Tuple[str, Optional[str]]:
    """Generate both Excel and PDF reports with comprehensive data."""
    from services.report_generator.logic.template_service import template_service

    safe_name = society_name.replace(" ", "_")
    excel_filename = f"Feasibility_{scheme}_{redevelopment_type}_{safe_name}.xlsx"
    excel_path = str(output_dir / excel_filename)

    excel_bytes, saved_path = template_service.generate_full_report(
        scheme=scheme,
        all_data=all_data,
        output_path=excel_path,
        redevelopment_type=redevelopment_type,
    )

    pdf_filename = f"Feasibility_{scheme}_{safe_name}.pdf"
    pdf_path = str(output_dir / pdf_filename)

    try:
        from services.report_generator.logic.pdf_builder import build_feasibility_pdf

        pdf_data = normalize_template_data_for_pdf(all_data)
        build_feasibility_pdf(pdf_data, pdf_path)
        logger.info(f"PDF generated: {pdf_path}")

    except Exception as e:
        logger.warning(f"PDF generation failed: {e}. Returning Excel only.")
        pdf_path = None

    return saved_path, pdf_path


def normalize_template_data_for_pdf(data: dict) -> dict:
    """Convert template service data to comprehensive pdf_builder format."""
    premium = data.get("premium", {})
    fsi = data.get("fsi", {})
    bua = data.get("bua", {})
    financial = data.get("financial", {})
    dp_report = data.get("dp_report", {})
    mcgm_property = data.get("mcgm_property", {})
    height = data.get("height", {})
    site_analysis = data.get("site_analysis", {})
    zone_regulations = data.get("zone_regulations", {})

    # Core calculations
    plot_sqm = mcgm_property.get("area_sqm", data.get("plot_area_sqm", 0))
    plot_sqft = plot_sqm * 10.764
    total_fsi = fsi.get("total_with_fungible", fsi.get("total_fsi", 0))
    max_bua = plot_sqft * total_fsi if total_fsi else 0
    const_rate = premium.get("construction_rate", 3800)
    sale_rate = financial.get("sale_rate_residential", 35000)
    saleable_area = bua.get("saleable_area_sqft", int(max_bua * 0.47))
    revenue = saleable_area * sale_rate
    premium_total = premium.get("grand_total", 0) or premium.get(
        "fsi_premium_total", 0
    ) + premium.get("tdr_total", 0) + premium.get("clubbing_charges", 0)
    property_value = premium.get("property_value", plot_sqft * 50000)

    # BUA breakdown
    rehab_area = bua.get("rehab_area_sqft", int(max_bua * 0.28))
    free_sale_area = bua.get("free_sale_area_sqft", int(max_bua * 0.47))
    parking_area = int(max_bua / 800)
    amenities_area = int(max_bua * 0.05)
    existing_area = bua.get(
        "existing_area_sqft",
        data.get("num_flats", 0) * 500 + data.get("num_commercial", 0) * 250,
    )

    # Detailed MCGM Charges
    mcgm_charges = {
        "scrutiny_fees": int(max_bua * 0.5),
        "cfo_fees": int(max_bua * 0.3),
        "approval_fees": int(max_bua * 0.2),
        "fire_noc": int(max_bua * 0.2),
        "environmental": 50000,
        "drainage": 25000,
        "water": 25000,
        "electrical": 25000,
        "total": int(max_bua * 1.5),
    }

    # Member entitlements (simulated from input)
    num_flats = data.get("num_flats", 0)
    num_commercial = data.get("num_commercial", 0)
    member_entitlements = {
        "existing_members": num_flats + num_commercial,
        "avg_carpet_sqm": 50,
        "existing_total_sqft": existing_area,
        "rehab_entitlement_sqft": rehab_area,
        "additional_area_pct": 0.25,
        "extra_entitlement_sqft": int(rehab_area * 0.25),
        "total_entitlement_sqft": rehab_area + int(rehab_area * 0.25),
    }

    return {
        # Basic info
        "society_name": data.get("society_name", ""),
        "ref_no": f"FEAS/{datetime.now().strftime('%Y%m%d')}",
        "date": datetime.now().strftime("%d %B %Y"),
        "property_desc": f"CHS Redevelopment under Scheme {data.get('scheme', '')}",
        "location": data.get("location", ""),
        "address_line1": data.get("location", ""),
        "address_line2": f"Ward: {data.get('ward', 'N/A')} | Zone: {dp_report.get('zone', 'N/A')} | TPS: {mcgm_property.get('tps_scheme', 'N/A')}",
        "ward": data.get("ward", ""),
        "zone": dp_report.get("zone", ""),
        "plot_area_sqm": plot_sqm,
        "road_width_m": dp_report.get("road_width_m", data.get("road_width_m", 0)),
        "num_flats": num_flats,
        "num_commercial": num_commercial,
        "society_short": data.get("society_name", "")[:20],
        # Collateral Details
        "cts_no": mcgm_property.get("cts_no", "To be verified"),
        "tp_scheme": mcgm_property.get("tps_scheme", "N/A"),
        "survey_no": mcgm_property.get("survey_no", "To be verified"),
        "village": mcgm_property.get("village", dp_report.get("village", "N/A")),
        # Units
        "commercial_units": [
            {
                "label": "Shop/Commercial",
                "count": num_commercial,
                "area_sqm": 25,
                "total_sqft": num_commercial * 269,
            }
        ],
        "residential_units": [
            {
                "label": "Flat/Residential",
                "count": num_flats,
                "area_sqm": 50,
                "total_sqft": num_flats * 538,
            }
        ],
        # Detailed FSI breakdown
        "fsi": {
            "33(7)(B)": {
                "zonal_fsi": fsi.get("base_fsi", 1.33),
                "base_fsi_area_sqft": int(plot_sqft * fsi.get("base_fsi", 1.33)),
                "add_fsi_premium": fsi.get("additional_fsi", 0.84),
                "add_fsi_area_sqft": int(plot_sqft * fsi.get("additional_fsi", 0.84)),
                "tdr_road_width": fsi.get("tdr", 0.83),
                "tdr_area_sqft": int(plot_sqft * fsi.get("tdr", 0.83)),
                "fungible": fsi.get("fungible", 0),
                "fungible_area_sqft": 0,
                "total_fsi": fsi.get("total_fsi", 4.05),
                "total_area_sqft": int(plot_sqft * fsi.get("total_fsi", 4.05)),
                "total_with_fungible": fsi.get("total_with_fungible", 5.40),
                "total_with_fungible_area": int(
                    plot_sqft * fsi.get("total_with_fungible", 5.40)
                ),
            },
            "33(20)(B)": {
                "zonal_fsi": fsi.get("base_fsi", 1.33),
                "base_fsi_area_sqft": int(plot_sqft * fsi.get("base_fsi", 1.33)),
                "add_fsi_premium": fsi.get("additional_fsi", 0.84),
                "add_fsi_area_sqft": int(plot_sqft * fsi.get("additional_fsi", 0.84)),
                "tdr_road_width": fsi.get("tdr", 0.83),
                "tdr_area_sqft": int(plot_sqft * fsi.get("tdr", 0.83)),
                "add_fsi_2020b": 0.50,
                "add_2020b_area_sqft": int(plot_sqft * 0.50),
                "fungible": fsi.get("fungible", 0.35),
                "fungible_area_sqft": int(plot_sqft * 0.35),
                "total_fsi": fsi.get("total_fsi", 4.05),
                "total_area_sqft": int(plot_sqft * fsi.get("total_fsi", 4.05)),
                "total_with_fungible": fsi.get("total_with_fungible", 5.40),
                "total_with_fungible_area": int(max_bua),
            },
            "33(11)": {
                "zonal_fsi": 1.33,
                "total_fsi": "—",
                "total_area_sqft": int(plot_sqft * 1.33),
                "fungible": "—",
                "total_with_fungible": "—",
            },
            "33(12)(B)": {
                "zonal_fsi": 1.33,
                "total_fsi": "—",
                "total_area_sqft": int(plot_sqft * 1.33),
                "fungible": "—",
                "total_with_fungible": "—",
            },
        },
        # Detailed BUA breakdown
        "bua": {
            "33(7)(B)": {
                "total_permissible_sqft": bua.get(
                    "total_permissible_sqft", int(max_bua * 0.74)
                ),
                "rehab_area_sqft": int(rehab_area * 0.74),
                "free_sale_sqft": int(free_sale_area * 0.74),
                "parking_sqft": int(parking_area * 0.74),
                "amenities_sqft": int(amenities_area * 0.74),
                "rera_carpet_sqft": bua.get("rera_carpet_sqft", int(max_bua * 0.6)),
                "existing_area_sqft": existing_area,
                "parking": int(max_bua / 800),
                "total_constr_sqft": int(max_bua * 0.74 * const_rate),
            },
            "33(20)(B)": {
                "total_permissible_sqft": bua.get(
                    "total_permissible_sqft", int(max_bua)
                ),
                "rehab_area_sqft": rehab_area,
                "free_sale_sqft": free_sale_area,
                "parking_sqft": parking_area,
                "amenities_sqft": amenities_area,
                "rera_carpet_sqft": bua.get("rera_carpet_sqft", int(max_bua * 0.8)),
                "existing_area_sqft": existing_area,
                "parking": int(max_bua / 800),
                "total_constr_sqft": int(max_bua * const_rate),
            },
            "33(11)": {
                "total_permissible_sqft": 0,
                "rera_carpet_sqft": 0,
                "parking": 0,
                "total_constr_sqft": 0,
            },
            "33(12)(B)": {
                "total_permissible_sqft": 0,
                "rera_carpet_sqft": 0,
                "parking": 0,
                "total_constr_sqft": 0,
            },
        },
        # Detailed Financial with MCGM charges
        "financial": {
            "33(7)(B)": {
                "const_total": int(max_bua * 0.74 * const_rate),
                "parking_cost": int(max_bua * 0.1 * const_rate),
                "const_subtotal": int(max_bua * 0.74 * const_rate * 1.18),
                "gst": int(max_bua * 0.74 * const_rate * 0.18),
                "const_with_gst": int(max_bua * 0.74 * const_rate * 1.18),
                "fsi_tdr_total": int(premium_total),
                "mcgm_scrutiny": mcgm_charges["scrutiny_fees"],
                "mcgm_cfo": mcgm_charges["cfo_fees"],
                "mcgm_approval": mcgm_charges["approval_fees"],
                "mcgm_fire": mcgm_charges["fire_noc"],
                "mcgm_environmental": mcgm_charges["environmental"],
                "mcgm_drainage": mcgm_charges["drainage"],
                "mcgm_water": mcgm_charges["water"],
                "mcgm_electrical": mcgm_charges["electrical"],
                "mcgm_total": mcgm_charges["total"],
                "prof_fees": int(max_bua * 125),
                "temp_total": num_flats * 1000 * 36,
                "stamp_total": int(property_value * 0.07),
                "redevelopment_total": int(
                    max_bua * 0.74 * const_rate * 1.18
                    + premium_total
                    + max_bua * 125
                    + num_flats * 1000 * 36
                    + mcgm_charges["total"]
                    + property_value * 0.07
                ),
            },
            "33(20)(B)": {
                "const_total": int(max_bua * const_rate),
                "parking_cost": int(max_bua * 0.1 * const_rate),
                "const_subtotal": int(max_bua * const_rate * 1.18),
                "gst": int(max_bua * const_rate * 0.18),
                "const_with_gst": int(max_bua * const_rate * 1.18),
                "fsi_tdr_total": int(premium_total),
                "mcgm_scrutiny": mcgm_charges["scrutiny_fees"],
                "mcgm_cfo": mcgm_charges["cfo_fees"],
                "mcgm_approval": mcgm_charges["approval_fees"],
                "mcgm_fire": mcgm_charges["fire_noc"],
                "mcgm_environmental": mcgm_charges["environmental"],
                "mcgm_drainage": mcgm_charges["drainage"],
                "mcgm_water": mcgm_charges["water"],
                "mcgm_electrical": mcgm_charges["electrical"],
                "mcgm_total": mcgm_charges["total"],
                "prof_fees": int(max_bua * 125),
                "temp_total": num_flats * 1000 * 36,
                "stamp_total": int(property_value * 0.07),
                "redevelopment_total": int(
                    max_bua * const_rate * 1.18
                    + premium_total
                    + max_bua * 125
                    + num_flats * 1000 * 36
                    + mcgm_charges["total"]
                    + property_value * 0.07
                ),
            },
        },
        # Member Entitlements
        "member_entitlements": member_entitlements,
        # Additional entitlement
        "additional_entitlement": {
            "33(7)(B)": {
                "cost_crore": (
                    max_bua * 0.74 * const_rate * 1.18
                    + premium_total
                    + max_bua * 125
                    + mcgm_charges["total"]
                )
                / 1e7,
                "rera_total_sqft": bua.get("rera_carpet_sqft", int(max_bua * 0.6)),
                "existing_sqft": existing_area,
                "sale_rate": sale_rate,
                "add_rera_pct": 0.25,
                "sale_area_sqft": saleable_area,
                "revenue_crore": revenue / 1e7,
                "gst_crore": 0,
                "profit_crore": (
                    revenue
                    - max_bua * 0.74 * const_rate * 1.18
                    - premium_total
                    - max_bua * 125
                    - mcgm_charges["total"]
                )
                / 1e7,
                "profit_pct": (
                    revenue
                    - max_bua * 0.74 * const_rate * 1.18
                    - premium_total
                    - max_bua * 125
                    - mcgm_charges["total"]
                )
                / revenue
                if revenue
                else 0,
            },
            "33(20)(B)": {
                "cost_crore": (
                    max_bua * const_rate * 1.18
                    + premium_total
                    + max_bua * 125
                    + mcgm_charges["total"]
                )
                / 1e7,
                "rera_total_sqft": bua.get("rera_carpet_sqft", int(max_bua * 0.8)),
                "existing_sqft": existing_area,
                "sale_rate": sale_rate,
                "add_rera_pct": 0.30,
                "sale_area_sqft": saleable_area,
                "revenue_crore": revenue / 1e7,
                "gst_crore": 0,
                "profit_crore": (
                    revenue
                    - max_bua * const_rate * 1.18
                    - premium_total
                    - max_bua * 125
                    - mcgm_charges["total"]
                )
                / 1e7,
                "profit_pct": (
                    revenue
                    - max_bua * const_rate * 1.18
                    - premium_total
                    - max_bua * 125
                    - mcgm_charges["total"]
                )
                / revenue
                if revenue
                else 0,
            },
        },
        # Comprehensive LLM Analysis
        "llm_analysis": f"""FEASIBILITY ANALYSIS SUMMARY - {data.get("scheme", "33(20)(B)")}

PROPERTY DETAILS:
• Society: {data.get("society_name", "N/A")}
• Location: {data.get("location", "N/A")}
• Plot Area: {plot_sqm:,.2f} sqm ({plot_sqft:,.0f} sqft)
• Road Width: {dp_report.get("road_width_m", 0)}m
• Zone: {dp_report.get("zone", "N/A")} | Ward: {data.get("ward", "N/A")}
• CTS No: {mcgm_property.get("cts_no", "To be verified")} | TPS: {mcgm_property.get("tps_scheme", "N/A")}

FSI CALCULATION (Scheme {data.get("scheme", "33(20)(B)")}):
• Base FSI (1.33): {int(plot_sqft * 1.33):,} sqft
• Additional FSI Premium: {int(plot_sqft * fsi.get("additional_fsi", 0.84)):,} sqft
• TDR (Road Width): {int(plot_sqft * fsi.get("tdr", 0.83)):,} sqft
• Additional FSI 2020(B): {int(plot_sqft * 0.50):,} sqft
• Fungible (35%): {int(plot_sqft * 0.35):,} sqft
• TOTAL PERMISSIBLE BUA: {int(max_bua):,} sqft

BUA AREA BREAKUP:
• Rehab Area: {rehab_area:,} sqft ({rehab_area / max_bua * 100:.1f}%)
• Free Sale Area: {free_sale_area:,} sqft ({free_sale_area / max_bua * 100:.1f}%)
• Parking: {parking_area:,} sqft
• Amenities: {amenities_area:,} sqft
• Existing Area: {existing_area:,} sqft
• RERA Carpet: {int(max_bua * 0.8):,} sqft

COST BREAKUP:
• Construction (incl GST 18%): Rs {max_bua * const_rate * 1.18 / 10000000:.2f} Cr
• FSI/TDR Premium: Rs {premium_total / 10000000:.2f} Cr
• MCGM Charges: Rs {mcgm_charges["total"] / 10000000:.2f} Cr
  - Scrutiny Fees: Rs {mcgm_charges["scrutiny_fees"] / 100000:.1f} L
  - CFO Approval: Rs {mcgm_charges["cfo_fees"] / 100000:.1f} L
  - Fire NOC: Rs {mcgm_charges["fire_noc"] / 100000:.1f} L
  - Environmental: Rs {mcgm_charges["environmental"] / 100000:.1f} L
• Professional Fees (@ Rs125/sqft): Rs {max_bua * 125 / 10000000:.2f} Cr
• Temp Accommodation (36 months): Rs {num_flats * 1000 * 36 / 10000000:.2f} Cr
• Stamp Duty (7%): Rs {property_value * 0.07 / 10000000:.2f} Cr
• TOTAL PROJECT COST: Rs {(max_bua * const_rate * 1.18 + premium_total + mcgm_charges["total"] + max_bua * 125 + num_flats * 1000 * 36 + property_value * 0.07) / 10000000:.2f} Cr

REVENUE & PROFIT:
• Saleable Area: {saleable_area:,} sqft @ Rs {sale_rate:,}/sqft
• Gross Revenue (Resi): Rs {revenue / 10000000:.2f} Cr
• Parking Revenue: Rs {num_commercial * financial.get("parking_sale_rate", 1000000) / 10000000:.2f} Cr
• TOTAL REVENUE: Rs {(revenue + num_commercial * financial.get("parking_sale_rate", 1000000)) / 10000000:.2f} Cr
• NET PROFIT: Rs {(revenue + num_commercial * financial.get("parking_sale_rate", 1000000) - max_bua * const_rate * 1.18 - premium_total - max_bua * 125 - mcgm_charges["total"] - num_flats * 1000 * 36 - property_value * 0.07) / 10000000:.2f} Cr

MEMBER ENTITLEMENTS:
• Existing Members: {num_flats + num_commercial}
• Avg Carpet Area: {member_entitlements["avg_carpet_sqm"]} sqm ({member_entitlements["avg_carpet_sqm"] * 10.764:.0f} sqft)
• Existing Total Area: {existing_area:,} sqft
• Rehab Entitlement: {rehab_area:,} sqft
• Additional 25%: {int(rehab_area * 0.25):,} sqft
• TOTAL ENTITLEMENT: {rehab_area + int(rehab_area * 0.25):,} sqft per member

SITE CONSTRAINTS:
• Max Building Height: {height.get("max_height_m", "N/A")}m ({height.get("max_floors", "N/A")} floors) - {height.get("aai_zone", "N/A")} zone
• CRZ Status: {zone_regulations.get("crz_zone", "N/A")}
• Metro Influence: {zone_regulations.get("metro_zone", "To be verified")}
• Setback Requirements: {zone_regulations.get("setback_requirements", "As per DCPR 2034")}
• DP Remarks: {dp_report.get("dp_remarks", "N/A")}
• Ready Reckoner Rate: Rs {premium.get("rr_rate", "N/A")}/sqm

REGULATORY NOTES:
• Allotment of additional floor space index under regulation 33(20)(B) is subject to conditions of D.C.P.R. 2034
• Construction in CRZ area requires CRZ clearance from MoEF
• Building height restriction applies as per AAI guidelines
• Premium charges are indicative and subject to revision by MCGM
• All calculations are provisional and tentative

NOTE: This feasibility is based on data provided by society. Actual costs subject to MCGM approval.""",
    }


