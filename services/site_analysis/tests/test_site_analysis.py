import asyncio

from utils import setup_path

setup_path("site_analysis")

from services.site_analysis.services.analyse import infer_area_type


async def test_site_analysis_flow():

    nearby = [{"name": "Shopping Mall", "types": ["store"]}]
    area_type = infer_area_type(nearby)
    assert area_type == "Predominantly Commercial"

    # This might call external APIs (Google Maps), so we just verify the logic works.


if __name__ == "__main__":
    asyncio.run(test_site_analysis_flow())
