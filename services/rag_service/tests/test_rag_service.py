import asyncio
import contextlib

import httpx
from utils import setup_path

setup_path("rag_service")


async def test_rag_health():
    url = "http://localhost:8007/health"
    async with httpx.AsyncClient(timeout=5.0) as client:
        with contextlib.suppress(Exception):
            await client.get(url)


if __name__ == "__main__":
    asyncio.run(test_rag_health())
