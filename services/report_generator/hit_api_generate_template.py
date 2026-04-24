import os
import sys
import time
from datetime import datetime
import httpx


def main():
    base_url = os.getenv("REPORT_BASE_URL", "http://127.0.0.1:8085")
    url = f"{base_url}/generate/template"

    payload = {
        "scheme": "33(7)(B)",
        "redevelopment_type": "CLUBBING",
        "society_name": "Testing template details",
        "num_flats": 37,
        "num_commercial": 0,
        "ready_reckoner": {
            "rr_open_land_sqm": 1228870
        },
        "financial": {
            "sale_rate_residential": 50000,
            "parking_price_per_unit": 1200000
        },
        "manual_inputs": {
            # Direct cell overrides based on the template positions
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

    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, json=payload)
        if r.status_code != 200:
            print(f"Request failed: {r.status_code} {r.text}")
            sys.exit(1)
        out_dir = os.path.join(os.sep, "tmp", "reports")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(out_dir, f"E2E_API_33_7B_{ts}.xlsx")
        with open(out_path, "wb") as f:
            f.write(r.content)
        print(out_path)


if __name__ == "__main__":
    main()

