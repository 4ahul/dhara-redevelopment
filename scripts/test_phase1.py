import asyncio
import json
import logging
from pathlib import Path

import httpx

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("Phase1Test")

# Real Mumbai inputs for scrapers
TEST_INPUT = {
    "society_name": "Testing Phase 1 — Dadar Realty",
    "address": "Dadar West, Mumbai, Maharashtra 400028",
    "district": "Mumbai City",
    "taluka": "Mumbai City",
    "village": "Dadar",
    "ward": "G/N",
    "cts_no": "1128",
}


async def fetch_real_data():
    """Fetch real data from the live microservices."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1. Site Analysis
        logger.info("📡 Step 1: Fetching Site Analysis (Coordinates)...")
        try:
            site_res = await client.post(
                "http://localhost:8001/analyse",
                json={"address": TEST_INPUT["address"], "ward": TEST_INPUT["ward"]},
            )
            site_data = site_res.json() if site_res.status_code == 200 else {"error": site_res.text}
            logger.info(f"✅ Site Analysis complete (Status: {site_res.status_code})")
        except Exception as e:
            logger.error(f"❌ Site Analysis failed: {e}")
            site_data = {"error": str(e)}

        # 2. PR Card Scraper
        logger.info("📡 Step 2: Fetching PR Card (Real Land Records)...")
        try:
            pr_res = await client.post(
                "http://localhost:8005/scrape/sync",
                json={
                    "district": TEST_INPUT["district"],
                    "taluka": TEST_INPUT["taluka"],
                    "village": TEST_INPUT["village"],
                    "survey_no": TEST_INPUT["cts_no"],
                },
            )
            pr_data = pr_res.json() if pr_res.status_code == 200 else {"error": pr_res.text}
            logger.info(f"✅ PR Card Scraper complete (Status: {pr_res.status_code})")
        except Exception as e:
            logger.error(f"❌ PR Card Scraper failed: {e}")
            pr_data = {"error": str(e)}

        # 3. MCGM Lookup
        logger.info("📡 Step 3: Fetching MCGM Data (Authoritative Spatial)...")
        try:
            mcgm_res = await client.post(
                "http://localhost:8007/lookup/sync",
                json={
                    "ward": TEST_INPUT["ward"],
                    "village": TEST_INPUT["village"],
                    "cts_no": TEST_INPUT["cts_no"],
                    "use_fp": False,
                },
            )
            mcgm_data = mcgm_res.json() if mcgm_res.status_code == 200 else {"error": mcgm_res.text}
            logger.info(f"✅ MCGM Lookup complete (Status: {mcgm_res.status_code})")
        except Exception as e:
            logger.error(f"❌ MCGM Lookup failed: {e}")
            mcgm_data = {"error": str(e)}

        # 4. DP Remarks
        logger.info("📡 Step 4: Fetching DP Remarks (Zoning & Roads)...")
        lat = site_data.get("lat") or mcgm_data.get("centroid_lat")
        lng = site_data.get("lng") or mcgm_data.get("centroid_lng")
        try:
            dp_res = await client.post(
                "http://localhost:8008/fetch/sync",
                json={
                    "ward": TEST_INPUT["ward"],
                    "village": TEST_INPUT["village"],
                    "cts_no": TEST_INPUT["cts_no"],
                    "lat": lat,
                    "lng": lng,
                    "use_fp_scheme": False,
                },
            )
            dp_data = dp_res.json() if dp_res.status_code == 200 else {"error": dp_res.text}
            logger.info(f"✅ DP Remarks complete (Status: {dp_res.status_code})")
        except Exception as e:
            logger.error(f"❌ DP Remarks failed: {e}")
            dp_data = {"error": str(e)}

        return {
            "site_analysis": site_data,
            "pr_card": pr_data,
            "mcgm_property": mcgm_data,
            "dp_report": dp_data,
        }


async def run_phase1():
    """Execute Phase 1 and generate the mapping test report."""
    logger.info("🚀 Starting Phased Testing: Phase 1 (Foundation Data)")

    real_data = await fetch_real_data()

    # Combined payload for report_generator
    mcgm = real_data.get("mcgm_property") or {}
    pr_card = real_data.get("pr_card") or {}
    dp = real_data.get("dp_report") or {}
    site = real_data.get("site_analysis") or {}

    # Ensure they are dicts even on failure
    if not isinstance(mcgm, dict):
        mcgm = {"error": str(mcgm)}
    if not isinstance(pr_card, dict):
        pr_card = {"error": str(pr_card)}
    if not isinstance(dp, dict):
        dp = {"error": str(dp)}
    if not isinstance(site, dict):
        site = {"error": str(site)}

    # Priority logic matching production orchestrator
    pr_extracted = pr_card.get("extracted_data") or {}
    if not isinstance(pr_extracted, dict):
        pr_extracted = {}

    plot_area_sqm = (
        pr_card.get("area_sqm") or pr_extracted.get("area_sqm") or mcgm.get("area_sqm") or 1000.0
    )

    road_width_m = dp.get("road_width_m") or site.get("road_width_m") or 18.3

    payload = {
        "society_name": TEST_INPUT["society_name"],
        "scheme": "33(7)(B)",
        "redevelopment_type": "CLUBBING",
        "ward": TEST_INPUT["ward"],
        "plot_area_sqm": float(plot_area_sqm),
        "road_width_m": float(road_width_m),
        "num_flats": int(
            pr_card.get("num_flats") or mcgm.get("building_data", {}).get("num_flats") or 0
        ),
        "num_commercial": int(
            pr_card.get("num_commercial")
            or mcgm.get("building_data", {}).get("num_commercial")
            or 0
        ),
        # Microservice Blobs
        "mcgm_property": mcgm,
        "dp_report": dp,
        "site_analysis": site,
        # Empty fields for other phases
        "height": {},
        "ready_reckoner": {},
        "financial": {},
        "manual_inputs": {},
        "premium": {},
        "zone_regulations": {},
        "fsi": {},
        "bua": {},
    }

    logger.info("📝 Step 5: Generating Mapping Test Report...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            res = await client.post(
                "http://localhost:8004/generate/feasibility-report", json=payload
            )
            if res.status_code == 200:
                out_path = Path("report_outputs/Phase1_RealData_Test.xlsx")
                out_path.parent.mkdir(exist_ok=True)
                out_path.write_bytes(res.content)
                logger.info(f"✅ Success! Phase 1 report saved to: {out_path.absolute()}")
                print(
                    f"\n--- DATA GATHERED SUMMARY ---\n{json.dumps({k: 'OK' if 'error' not in v else 'FAIL' for k, v in real_data.items()}, indent=2)}"
                )
            else:
                logger.error(f"❌ Report Generation Failed: {res.status_code}\n{res.text}")
        except Exception as e:
            logger.error(f"❌ Report Generation Request Failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_phase1())
