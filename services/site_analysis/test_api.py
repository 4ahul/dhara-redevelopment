import asyncio
import logging
import sys
import os

# Add service directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from services.site_analysis.services.analyse import site_analysis_service


async def test():
    logging.basicConfig(level=logging.INFO)
    address = "Sanjay CHS, Prabhadevi, Mumbai"
    print(f"Testing Site Analysis for: {address}")

    try:
        result = await site_analysis_service.analyse(address=address)
        print("\nAPI RESULT:")
        import json

        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"TEST FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(test())

