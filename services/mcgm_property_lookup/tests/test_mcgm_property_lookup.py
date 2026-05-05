import asyncio

import httpx
from utils import setup_path

setup_path("mcgm_property_lookup")


async def test_mcgm_property_lookup_flow():
    url = "http://localhost:8008/lookup/sync"
    payload = {"ward": "K/E", "village": "Chakala", "cts_no": "551"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                resp.json()
            else:
                pass
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(test_mcgm_property_lookup_flow())
