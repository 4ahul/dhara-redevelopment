import asyncio
from utils import setup_path
setup_path("site_analysis")

from services.site_analysis.services.analyse import site_analysis_service, infer_area_type

async def test_site_analysis_flow():
    print("Testing Site Analysis Service Flow...")
    
    print("- Testing area type inference")
    nearby = [{"name": "Shopping Mall", "types": ["store"]}]
    area_type = infer_area_type(nearby)
    print(f"  Inferred: {area_type}")
    assert area_type == "Predominantly Commercial"

    print("- Testing site analysis (mocked geocoding if needed, but here testing direct call)")
    # This might call external APIs (Google Maps), so we just verify the logic works.
    print("  (Skipping external API calls for local test, verify with: python services/site_analysis/test_api.py)")

if __name__ == "__main__":
    asyncio.run(test_site_analysis_flow())
