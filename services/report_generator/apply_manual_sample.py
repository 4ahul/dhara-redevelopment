"""
Apply a sample set of manual inputs to the 33(7)(B) template and save output.

Run:
  python -m services.report_generator.apply_manual_sample
"""

import os
import sys
from io import BytesIO

# Ensure local package imports resolve ('core', 'services')
BASE_DIR = os.path.dirname(__file__)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Also add project root so ``python -m services.report_generator.apply_manual_sample`` works
PROJ_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

from services.report_generator.services.template_service import template_service
from services.report_generator.services.cell_mapper import cell_mapper  # ensure package resolves
from services.report_generator.core.config import OUTPUT_DIR


def main():
    scheme = "33(7)(B)"
    rd = "CLUBBING"

    all_data = {
        "society_name": "Testing template details",
        "scheme": scheme,
        "num_flats": 37,
        "num_commercial": 0,
        "ready_reckoner": {
            "rr_open_land_sqm": 1228870,
        },
        "financial": {
            "sale_rate_residential": 50000,
            "parking_price_per_unit": 1200000,
        },
        "manual_inputs": {
            # Direct cell overrides for known positions in this template
            "Details!B19": 37,
            "Details!G34": 1.2,
            "Details!G39": 1.2,
            "Details!J45": 0,
            "Details!J54": 1228870,

            "Construction Cost!D8": 3800,
            "Construction Cost!D12": 3800,
            "Construction Cost!D15": 1700,
            "Construction Cost!H21": 2200,

            "SUMMARY 1!I27": 55000,
            "SUMMARY 1!I98": 1110000,
            "SUMMARY 1!I103": 200000,

            "Profit & Loss Statement!D28": 50000,
            "Profit & Loss Statement!C30": 75,
            "Profit & Loss Statement!D30": 1200000,

            "MCGM PAYMENTS!B277": 20,
        },
    }

    out_path = str(OUTPUT_DIR / "Feasibility_33_7B_maptest.xlsx")
    _, saved_path = template_service.generate_full_report(
        scheme=scheme,
        all_data=all_data,
        output_path=out_path,
        redevelopment_type=rd,
    )
    print(f"Wrote: {saved_path}")


if __name__ == "__main__":
    main()

