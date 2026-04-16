import asyncio
import httpx
from utils import setup_path
setup_path("mcgm_property_lookup")

async def test_mcgm_property_lookup_flow():
    print("Testing MCGM Property Lookup Service Flow...")
    url = "http://localhost:8008/lookup/sync"
    payload = {
        "ward": "K/E",
        "village": "Chakala",
        "cts_no": "551"
    }
    
    print(f"- Sending request to {url} for {payload}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload)
            print(f"  Status Code: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"  Response: {data}")
            else:
                print(f"  Service might not be running. Run it with: python services/mcgm_property_lookup/main.py")
        except Exception as e:
            print(f"  ERROR (Service probably not running): {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_mcgm_property_lookup_flow())
