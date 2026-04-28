"""
Full Agent Flow Simulation — End-to-End Test
Simulates Steps 0-7, hits the live report_generator service,
and verifies the output Excel report.
"""

import json

import httpx
import openpyxl

REPORT_URL = "http://127.0.0.1:8004"

# ── User Input ────────────────────────────────────────────────────────────────
society_data = {
    "society_name": "Shakti Apt & Swami Shivanand Apt CHS Ltd.",
    "ward": "K/E",
    "village": "CHAKALA",
    "cts_no": "551",
    "scheme": "33(7)(B)",
    "num_flats": 138,
    "num_commercial": 12,
    "existing_commercial_carpet_sqft": 4800,
    "existing_residential_carpet_sqft": 69300,
    "sale_rate_per_sqft": 35000,
}

# ── Simulated microservice outputs ────────────────────────────────────────────

step0 = {  # get_mcgm_property
    "status": "completed",
    "area_sqm": 9660.7,
    "centroid_lat": 19.1176,
    "centroid_lng": 72.8562,
    "tps_name": "TPS IV Andheri",
    "cts_no": "551,552,553,554",
    "village": "CHAKALA",
    "ward": "K/E",
    "fp_no": "FP-551",
}

step2 = {  # get_dp_remarks
    "status": "completed",
    "zone_code": "R1",
    "zone_name": "Residential Zone",
    "road_width_m": 18.3,
    "fsi": 3.0,
    "height_limit_m": 120,
    "reservations": [],
    "crz_zone": False,
    "heritage_zone": False,
    "reservation_area_sqm": 0,
    "setback_area_sqm": 0,
    "amenity_area_sqm": 0,
    "dp_remarks": "No adverse remarks. Plot in R1 zone.",
}

step3 = {  # analyse_site
    "lat": 19.1176,
    "lng": 72.8562,
    "formatted_address": "Chakala, Andheri East, Mumbai 400099",
    "area_type": "Predominantly Residential",
    "zone_inference": "K/East Ward",
    "nearby_landmarks": ["Andheri Station", "WEH Highway"],
}

step4 = {  # get_max_height
    "max_height_m": 120.0,
    "max_floors": 40,
    "restriction_reason": "NOCAS permissible",
    "aai_zone": "Yellow Zone",
    "rl_datum_m": 7.5,
}

step5 = {  # query_regulations
    "answer": "Under Reg 33(7)(B), base FSI 1.33...",
    "sources": [
        {"text": "DCPR 2034 Reg 33(7)(B)", "source": "DCPR 2034", "page": 142},
    ],
}

step6 = {  # calculate_premiums
    "scheme": "33(7)(B)",
    "rr_open_land_sqm": 75910,
    "rr_residential_sqm": 169360,
    "rr_rates": [
        {"category": "Open Land", "value": 75910},
        {"category": "Residential", "value": 169360},
    ],
    "line_items": [
        {"description": "Additional FSI Premium", "amount": 25000000},
        {"description": "Fungible Compensatory Area", "amount": 18000000},
        {"description": "Staircase Premium", "amount": 8000000},
        {"description": "Open Space Deficiency", "amount": 5000000},
        {"description": "Slum TDR Cost", "amount": 6000000},
    ],
    "total_fsi_tdr_premiums": 62000000,
    "total_mcgm_charges": 23000000,
    "grand_total": 85000000,
    "grand_total_crore": 8.5,
}


def run_test():
    print("=" * 60)
    print("  FULL AGENT FLOW SIMULATION — E2E TEST")
    print("=" * 60)
    print()

    # Log each step
    steps = [
        ("Step 0: get_mcgm_property", step0, f"area_sqm={step0['area_sqm']}"),
        (
            "Step 2: get_dp_remarks",
            step2,
            f"road={step2['road_width_m']}m, zone={step2['zone_code']}",
        ),
        ("Step 3: analyse_site", step3, f"addr={step3['formatted_address'][:40]}"),
        (
            "Step 4: get_max_height",
            step4,
            f"height={step4['max_height_m']}m/{step4['max_floors']}fl",
        ),
        ("Step 5: query_regulations", step5, f"sources={len(step5['sources'])}"),
        ("Step 6: calculate_premiums", step6, f"total={step6['grand_total_crore']} Cr"),
    ]
    for name, _, summary in steps:
        print(f"  {name} -> {summary}")
    print()

    # ── Step 7: Construct report tool call ────────────────────────────────────
    tool_args = {
        "scheme": society_data["scheme"],
        "society_name": society_data["society_name"],
        "plot_area_sqm": step0["area_sqm"],
        "road_width_m": step2["road_width_m"],
        "ward": society_data["ward"],
        "zone": step2["zone_code"],
        "num_flats": society_data["num_flats"],
        "num_commercial": society_data["num_commercial"],
        "existing_commercial_carpet_sqft": society_data["existing_commercial_carpet_sqft"],
        "existing_residential_carpet_sqft": society_data["existing_residential_carpet_sqft"],
        "sale_rate_per_sqft": society_data["sale_rate_per_sqft"],
        "mcgm_property": step0,
        "dp_report": step2,
        "site_analysis": step3,
        "height": step4,
        "premium": step6,
        "ready_reckoner": {
            "rr_open_land_sqm": step6["rr_open_land_sqm"],
            "rr_residential_sqm": step6["rr_residential_sqm"],
        },
        "zone_regulations": step5,
        "financial": {
            "sale_rate_residential": 35000,
            "sale_rate_commercial_gf": 75000,
            "sale_rate_commercial_1f": 60000,
            "parking_price_per_unit": 1000000,
        },
        "regulatory_sources": [
            {"clause": s["source"], "text": s["text"]} for s in step5["sources"]
        ],
        "manual_inputs": {},
        "llm_analysis": "Project viable under 33(7)(B). 9660.7 sqm plot with 18.3m road.",
    }

    print("Step 7: generate_feasibility_report -> POST /generate/template")
    print(f"  Payload: {len(json.dumps(tool_args)):,} chars")
    print()

    # ── Hit the service ───────────────────────────────────────────────────────
    resp = httpx.post(f"{REPORT_URL}/generate/template", json=tool_args, timeout=30)
    print(
        f"  HTTP {resp.status_code} | {len(resp.content):,} bytes | {resp.headers.get('content-type', '')}"
    )

    if resp.status_code != 200:
        print(f"  ERROR: {resp.text[:500]}")
        return

    out_path = "/tmp/full_flow_report.xlsx"
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"  Saved: {out_path}")
    print()

    # ── Verify the output ─────────────────────────────────────────────────────
    wb = openpyxl.load_workbook(out_path, data_only=False)

    print("=" * 60)
    print("  REPORT VERIFICATION")
    print("=" * 60)
    print()
    print(f"  Sheets: {wb.sheetnames}")
    print()

    ws = wb["Details"]
    ws_pnl = wb["Profit & Loss Statement"]
    ws_cc = wb["Construction Cost"]

    checks = [
        # (sheet_ref, cell, expected, description)
        (ws, "P4", 9660.7, "MCGM area_sqm -> Plot Area"),
        (ws, "R17", 18.3, "DP road_width_m -> Road Width"),
        (ws, "J54", 75910.0, "RR open_land_sqm -> RR Land Rate"),
        (ws, "P49", 138, "User num_flats -> Resi Tenements (O35 mapped to num_flats)"),
        (ws, "M18", 12, "User num_commercial -> Comm Tenements"),
        (ws, "Q47", 69300.0, "User resi_carpet_sqft -> Resi Carpet"),
        (ws, "O53", 4800.0, "User comm_carpet_sqft -> Comm Carpet"),
        (ws, "N19", 0.0, "DP reservation=0 -> Reservation"),
        (ws, "P7", 0.0, "DP setback=0 -> Setback"),
        (ws, "G34", 1.28, "Default -> Comm Multiplier"),
        (ws, "G39", 1.30, "Default -> Resi Multiplier"),
        (ws, "Q55", 36.0, "Default -> Completion months"),
        (ws_cc, "D8", 3600.0, "Default -> Const Rate Comm"),
        (ws_cc, "D12", 3600.0, "Default -> Const Rate Resi"),
        (ws_pnl, "D19", 75000.0, "Financial -> Sale Rate Comm GF"),
        (ws_pnl, "D20", 60000.0, "Financial -> Sale Rate Comm 1F"),
        (ws_pnl, "D28", 35000.0, "User sale_rate -> Sale Rate Resi"),
        (ws_pnl, "C30", 250, "Default -> Parking Units"),
        (ws_pnl, "D30", 1000000.0, "Financial -> Parking Price"),
    ]

    passed = 0
    failed = 0
    for sheet_ref, cell, expected, desc in checks:
        actual = sheet_ref[cell].value
        match = False
        if actual == expected:
            match = True
        elif isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            match = abs(float(actual) - float(expected)) < 0.01

        if match:
            passed += 1
            print(f"  PASS  {desc}")
        else:
            failed += 1
            print(f"  FAIL  {desc}  (expected={expected}, actual={actual})")

    print()

    # Check formulas are preserved
    formula_checks = [
        (ws, "P5", "Net plot area formula"),
        (ws, "J6", "Plot Area as per PR formula"),
        (ws, "J31", "Gross FSI formula"),
        (ws_cc, "I8", "Comm const cost formula"),
        (ws_pnl, "E28", "Revenue Resi formula"),
        (ws_pnl, "E32", "Total Revenue formula"),
    ]

    formula_ok = 0
    for sheet_ref, cell, desc in formula_checks:
        val = sheet_ref[cell].value
        is_formula = isinstance(val, str) and val.startswith("=")
        if is_formula:
            formula_ok += 1
        else:
            print(f"  FAIL  {desc} - {cell}={val} (expected formula)")

    print(f"  Formulas intact: {formula_ok}/{len(formula_checks)}")
    print()
    print("=" * 60)
    print(
        f"  RESULT: {passed}/{len(checks)} value checks passed, {formula_ok}/{len(formula_checks)} formulas OK"
    )
    if failed == 0 and formula_ok == len(formula_checks):
        print("  ★ ALL CHECKS PASSED — Report generation is accurate ★")
    else:
        print(f"  ✗ {failed} value check(s) failed")
    print("=" * 60)


if __name__ == "__main__":
    run_test()
