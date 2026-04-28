import asyncio

import httpx
from utils import setup_path

setup_path("report_generator")


async def test_report_gen_health():
    print("Testing Report Generator Service Health...")
    # Port might vary, assuming 8002 for example or just check if it's running
    url = "http://localhost:8005/health"
    print(f"- Checking {url}")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url)
            print(f"  Status: {resp.status_code}")
            print(f"  Response: {resp.json()}")
        except Exception:
            print("  Service not running on port 8005")


if __name__ == "__main__":
    asyncio.run(test_report_gen_health())
