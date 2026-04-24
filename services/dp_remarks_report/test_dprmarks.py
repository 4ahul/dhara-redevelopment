"""
Test script for DPRMarks portal workflow
"""

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def test_dprmarks():
    from services.dp_scraper import DPBrowserScraper, DPREMARKS_URL
    from core import settings
    from playwright.async_api import async_playwright

    # Set credentials
    settings.DPRMARKS_USERNAME = "Jigar001"
    settings.DPRMARKS_PASSWORD = os.getenv("TEST_DPRMARKS_PASSWORD", "placeholder_password")

    print(f"Testing with username: {settings.DPRMARKS_USERNAME}")

    # Create a dedicated browser for DPRMarks
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
    )
    page = await context.new_page()

    try:
        # Navigate directly to DPRMarks
        logger.info("Navigating to %s", DPREMARKS_URL)
        await page.goto(DPREMARKS_URL, timeout=90000, wait_until="domcontentloaded")
        await asyncio.sleep(8)

        logger.info("Page title: %s", await page.title())

        # Test login
        scraper = DPBrowserScraper(headless=False)

        logger.info("Testing login...")
        login_result = await scraper._dprmarks_login(page)
        logger.info("Login result: %s", login_result)

        if login_result:
            await asyncio.sleep(3)

            # Click report button
            logger.info("Clicking Report button...")
            await scraper._dprmarks_click_report(page)
            await asyncio.sleep(3)

            # Fill form - use 1/1024 as the CTS
            logger.info("Filling form with ward=A, village=FORT, cts_no=1/1024")
            fill_result = await scraper._dprmarks_fill_form(page, "A", "FORT", "1/1024")
            logger.info("Fill result: %s", fill_result)

            if fill_result:
                # Click Next
                logger.info("Clicking Next buttons...")
                next_result = await scraper._dprmarks_click_next(page)
                logger.info("Next result: %s", next_result)
                await asyncio.sleep(3)

                # Click Create Challan
                logger.info("Clicking Create Challan...")
                challan_result = await scraper._dprmarks_create_challan(page)
                logger.info("Challan result: %s", challan_result)

        # Take final screenshot
        screenshot = await page.screenshot()
        with open("final_result.png", "wb") as f:
            f.write(screenshot)
        logger.info("Screenshot saved to final_result.png")

        return {"login_success": login_result}

    except Exception as e:
        logger.error("Error: %s", e)
        import traceback

        traceback.print_exc()
        return {"error": str(e)}
    finally:
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    result = asyncio.run(test_dprmarks())
    print("Result:", result)
