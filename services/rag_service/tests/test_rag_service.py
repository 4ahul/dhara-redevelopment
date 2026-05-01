import asyncio

import httpx
from utils import setup_path

setup_path("rag_service")


async def test_rag_health():
    print("Testing RAG Service Health...")
    url = "http://localhost:8007/health"
    print(f"- Checking {url}")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url)
            print(f"  Status: {resp.status_code}")
            print(f"  Response: {resp.json()}")
        except Exception:
            print("  Service not running on port 8007")


if __name__ == "__main__":
    asyncio.run(test_rag_health())
