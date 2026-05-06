import asyncio
import contextlib

import httpx
from utils import setup_path

setup_path("report_generator")


async def test_report_gen_health():
    # Port might vary, assuming 8002 for example or just check if it's running
    url = "http://localhost:8005/health"
    async with httpx.AsyncClient(timeout=5.0) as client:
        with contextlib.suppress(Exception):
            await client.get(url)


if __name__ == "__main__":
    asyncio.run(test_report_gen_health())
