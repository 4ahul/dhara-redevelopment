import asyncio
import logging
import os
import sys

# Add service directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import contextlib

from services.site_analysis.services.analyse import site_analysis_service


async def test():
    logging.basicConfig(level=logging.INFO)
    address = "Sanjay CHS, Prabhadevi, Mumbai"

    with contextlib.suppress(Exception):
        await site_analysis_service.analyse(address=address)


if __name__ == "__main__":
    asyncio.run(test())
