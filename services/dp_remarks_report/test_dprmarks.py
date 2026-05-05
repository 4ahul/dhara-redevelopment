"""
Test script for DPRMarks portal workflow - High Level Scrape
"""

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def test_dprmarks():
    from services.dp_remarks_report.core import settings
    from services.dp_remarks_report.services.dp_scraper import DPBrowserScraper

    # Set credentials
    settings.DPRMARKS_USERNAME = "Dhara "
    settings.DPRMARKS_PASSWORD = "Dhara@123"

    scraper = DPBrowserScraper(headless=False)

    return await scraper.scrape(
        ward="K/W",
        village="VILE PARLE",
        cts_no="854",
        tps_scheme="TPS VILE PARLE NO. VI",
        fp_no="18",
    )


if __name__ == "__main__":
    result = asyncio.run(test_dprmarks())
