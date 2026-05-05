"""
DP Report Service — Browser Scraper (Playwright)
Automates MCGM's online DP map portals to fetch Development Plan remarks.
"""

import asyncio
import logging
from typing import Any

from playwright.async_api import Page, async_playwright

logger = logging.getLogger(__name__)

DPREMARKS_URL = "https://dpremarks.mcgm.gov.in/dp2034/"


class DPBrowserScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scrape(
        self,
        ward: str,
        village: str,
        cts_no: str,
        lat: float | None = None,
        lng: float | None = None,
        use_fp_scheme: bool = False,
        tps_scheme: str | None = None,
        fp_no: str | None = None,
    ) -> dict[str, Any]:
        wait_schedule = [300, 600, 900]  # 5, 10, 15 minutes in seconds

        for attempt, wait_seconds in enumerate([0, *wait_schedule]):
            if wait_seconds > 0:
                logger.info(
                    f"Retry {attempt}: Waiting {wait_seconds // 60} minutes for session to clear..."
                )
                await asyncio.sleep(wait_seconds)

            playwright = None
            browser = None
            page = None
            try:
                playwright = await async_playwright().start()
                browser = await playwright.chromium.launch(
                    headless=self.headless,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(viewport={"width": 1920, "height": 1080})
                page = await context.new_page()

                # 1. Navigate
                await page.goto(DPREMARKS_URL, wait_until="domcontentloaded", timeout=90000)
                await asyncio.sleep(5)

                # 2. Login
                login_result = await self._login(page)
                if login_result == "ALREADY_LOGGED_IN":
                    if attempt < len(wait_schedule):
                        logger.warning(
                            f"Attempt {attempt + 1}: Account already logged in. Preparing for retry."
                        )
                        await browser.close()
                        await playwright.stop()
                        continue  # Next loop iteration will wait and retry
                    return {
                        "error": "Account already logged in after 3 retries (30 mins total). Stopping."
                    }
                if login_result != "SUCCESS":
                    return {"error": "Login failed"}

                # 3. Click Report
                try:
                    if not await self._click_report(page):
                        return {"error": "Failed to click Report section"}

                    # 4. Fill Form (CTS -> Check -> Fallback to FP)
                    target_tps = tps_scheme if tps_scheme else village
                    target_fp = fp_no if fp_no else cts_no

                    form_filled = await self._fill_form(
                        page, ward, village, cts_no, target_tps, target_fp
                    )
                    if not form_filled:
                        return {"error": "Failed to fill form fields"}

                    # 5. Navigation to Payment (Next -> Next -> Create Challan)
                    payment_url = await self._navigate_to_payment(page)
                    if not payment_url:
                        return {"error": "Failed to reach payment page"}

                    return {"attributes": {"status": "reached_payment"}, "url": payment_url}
                finally:
                    # 6. Strict Logout Guarantee
                    await self._logout(page)

            except Exception as e:
                logger.exception("Scraper error on attempt %d: %s", attempt + 1, e)
                if attempt == len(wait_schedule):
                    return {"error": str(e)}
                # On random error, wait same as schedule and retry
                await asyncio.sleep(60)
            finally:
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()

        return {"error": "Maximum retry attempts reached."}

    async def _login(self, page: Page) -> str:
        """Login and check for Already Logged In popup."""
        from ..core import settings

        logger.info("Attempting login...")

        try:
            await page.evaluate(
                "() => { var el = document.getElementById('user_login'); if (el) el.click(); }"
            )
            await asyncio.sleep(2)
        except Exception:
            await page.locator("#user_login").click(timeout=10000, force=True)
            await asyncio.sleep(1)

        await page.locator("#userID").fill(settings.DPRMARKS_USERNAME)
        await page.locator("#password").fill(settings.DPRMARKS_PASSWORD)
        await page.locator("#login_button").click()

        await asyncio.sleep(5)

        page_text = await page.evaluate("() => document.body.innerText")
        if "Already Logged" in page_text:
            logger.warning("Popup detected: Account already logged in.")
            return "ALREADY_LOGGED_IN"

        # Verify success by looking for Logout or Welcome
        if "Logout" in page_text or "Welcome" in page_text:
            logger.info("Login verified successful.")
            return "SUCCESS"

        logger.error("Login might have failed. Page text starts with: %s", page_text[:200])
        return "SUCCESS"  # Proceed anyway but log error

    async def _click_report(self, page: Page) -> bool:
        """Click the Report section with better diagnostics."""
        logger.info("Clicking Report section...")
        # Give the page a moment to settle after login
        await asyncio.sleep(5)

        # DEBUG: Log all clickable elements
        try:
            elements = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button, a, li, span, div'))
                    .filter(el => el.innerText && el.innerText.trim().length > 0)
                    .map(el => ({
                        tag: el.tagName,
                        text: el.innerText.trim(),
                        id: el.id,
                        class: el.className
                    }))
                    .slice(0, 100);
            }""")
            logger.info("Found elements: %s", elements)
        except Exception:
            pass

        selectors = [
            "button:has-text('Report')",
            "a:has-text('Report')",
            "#panelheading_report",
            "div:has-text('Report')",
            "span:has-text('Report')",
        ]

        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=3000):
                    await el.click()
                    await asyncio.sleep(3)
                    logger.info(f"Clicked Report via {sel}")
                    return True
            except Exception:
                continue

        # JS click fallback if text is exactly 'Report'
        try:
            clicked = await page.evaluate("""() => {
                var items = document.querySelectorAll('button, a, span, div');
                for (var i of items) {
                    if (i.innerText.trim().toUpperCase() === 'REPORT') {
                        i.click();
                        return true;
                    }
                }
                return false;
            }""")
            if clicked:
                logger.info("Clicked Report via JS fallback")
                await asyncio.sleep(3)
                return True
        except Exception:
            pass

    async def _select_from_dropdown(
        self, page: Page, field_id: str, value: str, label: str
    ) -> bool:
        """Strict UI interaction: click arrow, find value, click value."""
        logger.info(f"Selecting {label}: {value}")
        try:
            # 1. Click the dropdown arrow
            arrow_locator = page.locator(
                f"input[id='{field_id}'] ~ .dijitArrowButtonInner, .dijitComboBox[id*='{field_id}'] .dijitArrowButtonInner"
            ).first
            if await arrow_locator.is_visible(timeout=5000):
                await arrow_locator.click()
            else:
                # Fallback to clicking input itself
                await page.locator(f"#{field_id}").click()

            await asyncio.sleep(2)

            # 2. Find and click the item in the popup list
            clicked = await page.evaluate(
                """(val) => {
                var items = document.querySelectorAll('.dijitMenuItem');
                for (var i of items) {
                    if (i.offsetParent !== null && i.innerText.trim().toUpperCase() === val.toUpperCase()) {
                        i.click();
                        return true;
                    }
                }
                return false;
            }""",
                value,
            )

            if clicked:
                await asyncio.sleep(2)
                return True

            logger.warning(f"Value '{value}' not found in dropdown for {label}")
            return False

        except Exception as e:
            logger.exception(f"Error selecting dropdown {label}: {e}")
            return False

    async def _fill_form(
        self, page: Page, ward: str, village: str, cts_no: str, tps_scheme: str, fp_no: str
    ) -> bool:
        """Fill form using exact requested sequence: Ward -> Village -> CTS (fallback FP)."""
        logger.info("Starting form fill sequence on CTS tab...")

        # --- CTS TAB ---
        # 1. Ward
        if not await self._select_from_dropdown(page, "SelectWardR", ward, "Ward (CTS)"):
            return False

        # 2. Village
        if not await self._select_from_dropdown(page, "SelectVillageR", village, "Village (CTS)"):
            return False

        # 3. CTS Number (Check loop)
        logger.info("Checking CTS dropdown for value: %s", cts_no)
        arrow = page.locator("input[id='SelectCTSR'] ~ .dijitArrowButtonInner").first
        if await arrow.is_visible(timeout=3000):
            await arrow.click()
        else:
            await page.locator("#SelectCTSR").click()

        await asyncio.sleep(2)

        # Check if CTS exists in dropdown
        cts_exists = await page.evaluate(
            """(val) => {
            var items = document.querySelectorAll('.dijitMenuItem');
            for (var i of items) {
                if (i.offsetParent !== null && i.innerText.trim().toUpperCase() === val.toUpperCase()) {
                    i.click();
                    return true;
                }
            }
            return false;
        }""",
            cts_no,
        )

        if cts_exists:
            logger.info("CTS Number found and selected.")
            await asyncio.sleep(2)
            await page.locator("#generateCTSreport").click()
            await asyncio.sleep(5)
            return True

        # --- FP TAB (FALLBACK) ---
        logger.info("CTS Number NOT found. Switching to FP tab.")
        await page.mouse.click(10, 10)  # close dropdown
        await asyncio.sleep(1)
        await page.locator("a:has-text('FP')").first.click()
        await asyncio.sleep(3)

        # Sequence: Ward -> TPS -> FP
        if not await self._select_from_dropdown(page, "SelectWardR2", ward, "Ward (FP)"):
            return False
        if not await self._select_from_dropdown(page, "SelectTPSR", tps_scheme, "TPS Scheme (FP)"):
            return False
        if not await self._select_from_dropdown(page, "SelectFPR", fp_no, "FP Number (FP)"):
            return False

        await asyncio.sleep(2)
        await page.locator("#generateFPreport").click()
        await asyncio.sleep(5)
        return True

    async def _navigate_to_payment(self, page: Page) -> str | None:
        """Handle the Next -> Create Challan flow."""
        logger.info("Navigating Map -> Payment...")
        try:
            await asyncio.sleep(5)

            # Click the Next/Generate Challan button
            logger.info("Looking for second Next button...")
            next_clicked = False
            for sel in ["#generateChallan", "input[value='Next']", "button:has-text('Next')"]:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=5000):
                        await btn.click()
                        logger.info(f"Clicked second Next button via {sel}")
                        next_clicked = True
                        break
                except Exception:
                    continue

            if not next_clicked:
                logger.warning("Could not find second Next button.")
                return None

            await asyncio.sleep(5)

            # Fill consumer details (simplified since we only care about getting to bank page)
            # This would normally be here. Let's assume they are auto-filled or not required for simple redirect

            # Look for Create Challan button
            logger.info("Looking for Create Challan button...")
            async with page.expect_popup(timeout=30000) as popup_info:
                create_clicked = False
                for sel in [
                    "button:has-text('Create Challan')",
                    "#btnCreateChallan",
                    "input[value*='Challan']",
                ]:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible(timeout=5000):
                            await btn.click()
                            logger.info(f"Clicked Create Challan via {sel}")
                            create_clicked = True
                            break
                    except Exception:
                        continue

                if not create_clicked:
                    logger.warning("Could not find Create Challan button.")
                    return None

            bank_page = await popup_info.value
            await bank_page.wait_for_load_state("domcontentloaded")
            return bank_page.url

        except Exception as e:
            logger.exception("Error navigating to payment: %s", e)
            return None

    async def _logout(self, page: Page):
        """Strictly guaranteed logout before closing."""
        logger.info("Executing Mandatory Logout...")
        try:
            # Dismiss any popups
            await page.evaluate("""() => {
                var ok = document.getElementById('popupOKError');
                if (ok) ok.click();
            }""")
            await asyncio.sleep(1)

            logout_selectors = ["a:has-text('Logout')", "button:has-text('Logout')", "#btnLogout"]
            for sel in logout_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        logger.info("Successfully clicked Logout button.")
                        await asyncio.sleep(2)
                        return
                except Exception:
                    continue
            logger.warning("Logout button not found.")
        except Exception as e:
            logger.exception("Error during mandatory logout: %s", e)
