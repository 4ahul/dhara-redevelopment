import asyncio
from playwright.async_api import async_playwright


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to site...")
        await page.goto("https://bhulekh.mahabhumi.gov.in/")
        await asyncio.sleep(5)

        # Text before
        text_before = await page.inner_text("body")
        print("--- BEFORE ---")
        print(text_before[:1000])

        # Select English
        print("Selecting English...")
        try:
            await page.select_option("#ContentPlaceHolder1_ddllangforAll", "1")
            await page.evaluate(
                '() => document.querySelector("#ContentPlaceHolder1_ddllangforAll").dispatchEvent(new Event("change"))'
            )
            await asyncio.sleep(10)  # Wait longer for reload
        except Exception as e:
            print(f"Selection error: {e}")

        # Text after
        text_after = await page.inner_text("body")
        print("--- AFTER ---")
        print(text_after[:1000])

        # Check if "Property Card" text is present in English
        if "Property Card" in text_after:
            print("SUCCESS: 'Property Card' found in English UI!")
        else:
            print("FAILURE: 'Property Card' NOT found in UI.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
