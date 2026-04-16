"""
DP Report Service — Browser Scraper (Playwright)
Automates MCGM's online DP map portals to fetch Development Plan remarks.

Primary targets (tried in order):
  1. https://mcgmapp.mcgm.gov.in/DP2034/ — MCGM DP 2034 public viewer
  2. MCGM ArcGIS WebApp (zone layer) — intercepts /identify or /query responses
  3. AutoDCR portal (https://autodcr.mcgm.gov.in) — requires credentials
  4. DPRMarks portal (https://dpremarks.mcgm.gov.in/dp2034/) — requires credentials, workflow: login -> report -> ward/village/CTS -> next -> next -> create challan

The scraper intercepts ArcGIS network responses to capture raw JSON data
rather than relying on fragile DOM parsing.
"""

import asyncio
import base64
import json
import logging
from typing import Optional

from playwright.async_api import Page, Response, async_playwright

logger = logging.getLogger(__name__)

# DP 2034 public map
DP_MAP_URL = "https://mcgmapp.mcgm.gov.in/DP2034/"

# DPRMarks portal (requires login)
DPREMARKS_URL = "https://dpremarks.mcgm.gov.in/dp2034/"

# Fallback: MCGM ArcGIS portal main app (has DP layer)
MCGM_ARCGIS_URL = (
    "https://mcgm.maps.arcgis.com/apps/webappviewer/index.html"
    "?id=3a5c0a98a75341b985c10700dec6c4b8"
)

APP_LOAD_TIMEOUT = 60_000  # ms
RESPONSE_WAIT_TIMEOUT = 30  # seconds


class DPBrowserScraper:
    """Playwright-based scraper for MCGM DP 2034 zone data."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scrape(
        self,
        ward: str,
        village: str,
        cts_no: str,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> dict:
        """
        Attempt to scrape DP remarks.

        Returns dict with keys:
          - attributes: raw zone attributes dict or None
          - screenshot_b64: base64 PNG or None
          - error: error string or None
        """
        playwright = None
        browser = None
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            # Apply stealth if available
            page = await context.new_page()
            try:
                from playwright_stealth import Stealth

                await Stealth().apply_stealth_async(page)
            except Exception:
                pass

            result = await self._run(page, ward, village, cts_no, lat, lng)
            return result

        except Exception as e:
            logger.error("DP browser scraper fatal error: %s", e, exc_info=True)
            return {"attributes": None, "screenshot_b64": None, "error": str(e)}
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()

    async def _run(
        self,
        page: Page,
        ward: str,
        village: str,
        cts_no: str,
        lat: Optional[float],
        lng: Optional[float],
    ) -> dict:
        """Full scrape flow."""
        captured_data: list[dict] = []

        # ── 1. Intercept ArcGIS identify/query responses ───────────────────
        async def _on_response(response: Response):
            url = response.url.lower()
            if not any(k in url for k in ("/identify", "/query", "/find")):
                return
            if "json" not in response.headers.get("content-type", ""):
                return
            try:
                body = await response.json()
            except Exception:
                return
            # Capture identify results
            results = body.get("results", body.get("features", []))
            for item in results:
                attrs = item.get("attributes", item.get("value", {}))
                if isinstance(attrs, dict) and attrs:
                    # Filter for DP zone data (look for zone-related keys)
                    keys_upper = {k.upper() for k in attrs}
                    zone_keys = {
                        "ZONE",
                        "ZONE_CODE",
                        "LANDUSE",
                        "LAND_USE",
                        "DP_ZONE",
                        "ZONE_NAME",
                        "RESERVATION",
                        "DP_REMARKS",
                        "FSI",
                    }
                    if keys_upper & zone_keys:
                        logger.info(
                            "Captured DP zone data from %s: keys=%s",
                            response.url[:80],
                            list(keys_upper)[:5],
                        )
                        captured_data.append(attrs)

        page.on("response", lambda r: asyncio.ensure_future(_on_response(r)))

        # ── 2. Try the DP 2034 public map first ───────────────────────────
        logger.info("Navigating to MCGM DP 2034 map...")
        result = await self._try_dp_map(
            page, ward, village, cts_no, lat, lng, captured_data
        )
        if result.get("attributes") or result.get("screenshot_b64"):
            return result

        # ── 3. Fallback: MCGM ArcGIS WebApp ──────────────────────────────
        logger.info("Falling back to MCGM ArcGIS WebApp...")
        result = await self._try_arcgis_webapp(
            page, ward, village, cts_no, lat, lng, captured_data
        )
        if result.get("attributes") or result.get("screenshot_b64"):
            return result

        # ── 4. Fallback: DPRMarks portal (https://dpremarks.mcgm.gov.in/dp2034/) ─────
        logger.info("Falling back to DPRMarks portal...")
        return await self._try_dprmarks_portal(
            page, ward, village, cts_no, lat, lng, captured_data
        )

    async def _try_dp_map(
        self,
        page: Page,
        ward: str,
        village: str,
        cts_no: str,
        lat: Optional[float],
        lng: Optional[float],
        captured_data: list,
    ) -> dict:
        """Navigate the MCGM DP 2034 public viewer."""
        try:
            await page.goto(
                DP_MAP_URL, timeout=APP_LOAD_TIMEOUT, wait_until="domcontentloaded"
            )
        except Exception as e:
            logger.warning("DP map navigation failed: %s", e)
            return {"attributes": None, "screenshot_b64": None, "error": None}

        await asyncio.sleep(3)

        # If lat/lng given, click at the point on the map to trigger identify
        if lat is not None and lng is not None:
            success = await self._click_map_at_coords(page, lat, lng)
            if success:
                await asyncio.sleep(3)

        # Try CTS search if the page has a search widget
        await self._try_cts_search(page, ward, village, cts_no)
        await asyncio.sleep(3)

        screenshot_b64 = await self._screenshot(page)

        if captured_data:
            return {
                "attributes": captured_data[0],
                "screenshot_b64": screenshot_b64,
                "error": None,
            }

        # Try to read popup/tooltip text as fallback
        popup_text = await self._read_popup_text(page)
        if popup_text:
            attrs = _parse_popup_text(popup_text)
            if attrs:
                return {
                    "attributes": attrs,
                    "screenshot_b64": screenshot_b64,
                    "error": None,
                }

        return {"attributes": None, "screenshot_b64": screenshot_b64, "error": None}

    async def _try_arcgis_webapp(
        self,
        page: Page,
        ward: str,
        village: str,
        cts_no: str,
        lat: Optional[float],
        lng: Optional[float],
        captured_data: list,
    ) -> dict:
        """Navigate the MCGM ArcGIS WebApp and look for DP zone info."""
        try:
            await page.goto(
                MCGM_ARCGIS_URL, timeout=APP_LOAD_TIMEOUT, wait_until="domcontentloaded"
            )
        except Exception as e:
            logger.warning("MCGM ArcGIS navigation failed: %s", e)
            return {
                "attributes": None,
                "screenshot_b64": None,
                "error": f"Could not load MCGM portals: {e}",
            }

        await asyncio.sleep(5)

        # If lat/lng given, try clicking at the coordinate on the map
        if lat is not None and lng is not None:
            await self._click_map_at_coords(page, lat, lng)
            await asyncio.sleep(3)

        screenshot_b64 = await self._screenshot(page)

        if captured_data:
            return {
                "attributes": captured_data[0],
                "screenshot_b64": screenshot_b64,
                "error": None,
            }

        return {
            "attributes": None,
            "screenshot_b64": screenshot_b64,
            "error": "DP zone data not captured from browser automation",
        }

    async def _click_map_at_coords(self, page: Page, lat: float, lng: float) -> bool:
        """
        Click on the map at the given WGS84 coordinates.
        This works if the map has a coordinate-based navigate/identify feature.
        We use the ArcGIS JS API's goto mechanism via JavaScript injection.
        """
        try:
            # Inject a JS click on the map view center at the given coordinate
            await page.evaluate(
                """([lng, lat]) => {
                    // Try Esri JS 4.x map view
                    const views = window.__esriMapViews__ || [];
                    if (views.length) {
                        views[0].goTo({ center: [lng, lat], zoom: 17 });
                        return;
                    }
                    // Try to find mapView on the app
                    if (window.jimuConfig && window.jimuConfig.mapId) {
                        const map = document.querySelector('#' + window.jimuConfig.mapId);
                        if (map && map.__mapView) {
                            map.__mapView.goTo({ center: [lng, lat], zoom: 17 });
                        }
                    }
                }""",
                [lng, lat],
            )
            await asyncio.sleep(2)
            logger.info("Map navigated to lat=%s lng=%s", lat, lng)
            return True
        except Exception as e:
            logger.debug("Map navigation via JS failed: %s", e)
        return False

    async def _try_cts_search(
        self, page: Page, ward: str, village: str, cts_no: str
    ) -> bool:
        """Attempt to search by CTS number in the DP map's search widget."""
        # Look for a search input
        for sel in [
            "input[placeholder*='CTS']",
            "input[placeholder*='Search']",
            "input[placeholder*='Plot']",
            "input[type='search']",
            "input[type='text']",
        ]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.triple_click()
                    await el.type(f"{ward} {cts_no}", delay=50)
                    await page.keyboard.press("Enter")
                    logger.info("Searched for CTS in DP map via selector: %s", sel)
                    return True
            except Exception:
                continue
        return False

    async def _read_popup_text(self, page: Page) -> Optional[str]:
        """Try to read text from an info popup after a map click."""
        popup_selectors = [
            ".esri-popup__content",
            ".esri-popup",
            ".popup-content",
            ".info-window-content",
            "[class*='popup']",
            "[class*='infoWindow']",
        ]
        for sel in popup_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=3000):
                    text = await el.text_content()
                    if text and len(text.strip()) > 10:
                        logger.info("Found popup text (%d chars)", len(text))
                        return text.strip()
            except Exception:
                continue
        return None

    async def _screenshot(self, page: Page) -> Optional[str]:
        try:
            png = await page.screenshot(full_page=False)
            return base64.b64encode(png).decode()
        except Exception as e:
            logger.warning("Screenshot failed: %s", e)
            return None

    async def _try_dprmarks_portal(
        self,
        page: Page,
        ward: str,
        village: str,
        cts_no: str,
        lat: Optional[float],
        lng: Optional[float],
        captured_data: list,
    ) -> dict:
        """
        Navigate the DPRMarks portal (https://dpremarks.mcgm.gov.in/dp2034/)
        Workflow: login -> Report button -> ward/village/CTS -> next -> next -> create challan
        """
        from core import settings

        try:
            # Use JavaScript evaluation to navigate instead of page.goto
            # This avoids the redirect issue
            await page.evaluate(f"window.location.href = '{DPREMARKS_URL}'")
            await asyncio.sleep(10)
        except Exception as e:
            logger.warning("DPRMarks portal navigation failed: %s", e)
            return {"attributes": None, "screenshot_b64": None, "error": None}

        await asyncio.sleep(3)

        # ── Step 1: Login ──────────────────────────────────────────────────
        login_success = await self._dprmarks_login(page)
        if not login_success:
            return {
                "attributes": None,
                "screenshot_b64": await self._screenshot(page),
                "error": "Failed to login to DPRMarks portal",
            }

        # ── Step 2: Click Report button ─────────────────────────────────────
        report_success = await self._dprmarks_click_report(page)
        if not report_success:
            return {
                "attributes": None,
                "screenshot_b64": await self._screenshot(page),
                "error": "Failed to click Report button",
            }

        # ── Step 3: Fill ward, village/division, CTS ────────────────────────
        fill_success = await self._dprmarks_fill_form(page, ward, village, cts_no)
        if not fill_success:
            return {
                "attributes": None,
                "screenshot_b64": await self._screenshot(page),
                "error": "Failed to fill form fields",
            }

        # ── Step 4: Click Next buttons ───────────────────────────────────────
        next_success = await self._dprmarks_click_next(page)
        if not next_success:
            return {
                "attributes": None,
                "screenshot_b64": await self._screenshot(page),
                "error": "Failed to proceed through Next steps",
            }

        # ── Step 5: Click Create Challan ─────────────────────────────────────
        challan_result = await self._dprmarks_create_challan(page)

        # ── Step 6: Download & parse PDF (when payment automation is ready) ──
        # TODO: Uncomment when browser automation can complete payment and download PDF
        # pdf_bytes = await self._download_report_pdf(page)
        # if pdf_bytes:
        #     from .dp_pdf_parser import parse_dp_pdf
        #     parsed = parse_dp_pdf(pdf_bytes)
        #     if parsed.get("report_type"):
        #         return {
        #             "attributes": parsed,
        #             "screenshot_b64": await self._screenshot(page),
        #             "error": None,
        #             "pdf_bytes": pdf_bytes,
        #         }

        screenshot_b64 = await self._screenshot(page)

        if captured_data:
            return {
                "attributes": captured_data[0],
                "screenshot_b64": screenshot_b64,
                "error": None,
                "challan_data": challan_result,
            }

        # Parse any data from the challan page
        page_text = await self._read_dprmarks_page_text(page)
        if page_text:
            attrs = _parse_popup_text(page_text)
            if attrs:
                return {
                    "attributes": attrs,
                    "screenshot_b64": screenshot_b64,
                    "error": None,
                    "challan_data": challan_result,
                }

        return {
            "attributes": None,
            "screenshot_b64": screenshot_b64,
            "error": "Could not extract DP data from DPRMarks portal",
            "challan_data": challan_result,
        }

    async def _dprmarks_login(self, page: Page) -> bool:
        """Login to DPRMarks portal with credentials from settings."""
        from core import settings

        username = settings.DPRMARKS_USERNAME
        password = settings.DPRMARKS_PASSWORD

        if not username or not password:
            logger.warning("DPRMarks credentials not configured")
            return False

        try:
            # First, click the Login link using JavaScript to open the login form
            await page.evaluate("""() => {
                const el = document.getElementById('user_login');
                if (el) el.click();
            }""")
            logger.info("Clicked login link via JavaScript")
            await asyncio.sleep(2)

            # Now fill the form
            # Fill username
            user_id_el = page.locator("input[id='userID']").first
            if await user_id_el.is_visible(timeout=3000):
                await user_id_el.fill(username)
                logger.info("Filled username")

            # Fill password
            password_el = page.locator("input[id='password']").first
            if await password_el.is_visible(timeout=3000):
                await password_el.fill(password)
                logger.info("Filled password")

            # Click login/submit button
            submit_el = page.locator("button[id='login_button']").first
            if await submit_el.is_visible(timeout=3000):
                await submit_el.click()
                logger.info("Clicked login button")
                await asyncio.sleep(5)

                # After login, manually trigger the checkautoDCR function
                # to show the report button since the onload event already fired
                await page.evaluate("""() => {
                    // Set appauth to '1' to indicate authenticated
                    document.getElementById('appauth').value = '1';
                    // Show the report elements
                    var gisdata = document.getElementById('gisdata');
                    if (gisdata) gisdata.style.display = 'block';
                    var reportDiv = document.getElementById('reportDiv');
                    if (reportDiv) reportDiv.style.display = 'block';
                    var panelbody_report = document.getElementById('panelbody_report');
                    if (panelbody_report) panelbody_report.style.display = 'block';
                }""")
                logger.info("Manually showed report elements")

                return True

            return False

        except Exception as e:
            logger.error("DPRMarks login error: %s", e)
            return False

    async def _dprmarks_click_report(self, page: Page) -> bool:
        """Click the Report button (right side to search icon after login)."""
        try:
            for sel in [
                "button:has-text('Report')",
                "a:has-text('Report')",
                "li:has-text('Report')",
                "[id*='report']",
                "[class*='report']",
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3000):
                        await el.click()
                        logger.info("Clicked Report button")
                        await asyncio.sleep(2)
                        return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.error("DPRMarks report click error: %s", e)
            return False

    async def _dprmarks_fill_form(
        self, page: Page, ward: str, village: str, cts_no: str
    ) -> bool:
        """Fill ward, village/division, CTS fields in the report form."""
        try:
            # Wait for the loading to finish first
            logger.info("Waiting for loading to finish...")
            try:
                await page.wait_for_selector(
                    "#loadingImg", state="hidden", timeout=60000
                )
                logger.info("Loading finished")
            except Exception as e:
                logger.warning("Loading wait failed (continuing anyway): %s", e)

            await asyncio.sleep(2)

            # For the dropdowns, we need to use the dijit widget IDs
            # SelectWardR, SelectVillageR, SelectCTSR

            # Try to click and select Ward from dropdown
            try:
                # Click on the Ward dropdown to open it
                ward_dropdown = page.locator("input[id='SelectWardR']").first
                if await ward_dropdown.is_visible(timeout=3000):
                    await ward_dropdown.click()
                    await asyncio.sleep(1)
                    # Type the ward value to filter
                    await ward_dropdown.fill(ward)
                    await asyncio.sleep(1)
                    # Press arrow down and enter to select first match
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                    logger.info(f"Selected ward: {ward}")
            except Exception as e:
                logger.warning(f"Could not select ward: {e}")

            # Select Village/Division
            try:
                village_dropdown = page.locator("input[id='SelectVillageR']").first
                if await village_dropdown.is_visible(timeout=3000):
                    await village_dropdown.click()
                    await asyncio.sleep(1)
                    await village_dropdown.fill(village)
                    await asyncio.sleep(1)
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                    logger.info(f"Selected village: {village}")
            except Exception as e:
                logger.warning(f"Could not select village: {e}")

            # Select CTS
            try:
                cts_dropdown = page.locator("input[id='SelectCTSR']").first
                if await cts_dropdown.is_visible(timeout=3000):
                    await cts_dropdown.click()
                    await asyncio.sleep(1)
                    await cts_dropdown.fill(cts_no)
                    await asyncio.sleep(1)
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                    logger.info(f"Selected CTS: {cts_no}")
            except Exception as e:
                logger.warning(f"Could not select CTS: {e}")

            return True

        except Exception as e:
            logger.error("DPRMarks form fill error: %s", e)
            return False

    async def _dprmarks_click_next(self, page: Page) -> bool:
        """Click Next buttons to proceed through the workflow."""
        try:
            clicked = False

            # Wait for loading to finish
            try:
                await page.wait_for_selector(
                    "#loadingImg", state="hidden", timeout=60000
                )
            except Exception:
                pass

            # Click the "Next" button which has id="generateCTSreport" or "generateFPreport"
            for sel in [
                "button[id='generateCTSreport']",
                "button:has-text('Next')",
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3000):
                        await el.click()
                        logger.info("Clicked Next button")
                        await asyncio.sleep(5)
                        clicked = True
                        break
                except Exception:
                    continue

            # Wait for the CTS/FP selection section to load and select from dropdown
            await asyncio.sleep(3)

            # Look for the dropdown with selected CTS and select it
            try:
                # The second dropdown should have the selected CTS value
                cts_select = page.locator("input[id='SelectCTSR']").first
                if await cts_select.is_visible(timeout=5000):
                    # Click to open dropdown and select
                    await cts_select.click()
                    await asyncio.sleep(1)
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                    logger.info("Selected CTS from second dropdown")
            except Exception as e:
                logger.warning(f"Could not select from second CTS dropdown: {e}")

            # Look for the second "Next" button which appears after CTS selection
            for sel in [
                "button[id='generateChallan']",
                "input[value='Next']",
                "button:has-text('Next')",
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=5000):
                        await el.click()
                        logger.info("Clicked second Next button")
                        await asyncio.sleep(3)
                        clicked = True
                        break
                except Exception:
                    continue

            return clicked
        except Exception as e:
            logger.error("DPRMarks Next click error: %s", e)
            return False

    async def _dprmarks_create_challan(self, page: Page) -> dict:
        """Click Create Challan and capture the result data."""
        result = {"created": False, "data": None}
        try:
            for sel in [
                "button:has-text('Create Challan')",
                "input[value='Create Challan']",
                "a:has-text('Create Challan')",
                "[id*='challan']",
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3000):
                        await el.click()
                        logger.info("Clicked Create Challan button")
                        await asyncio.sleep(3)
                        result["created"] = True
                        break
                except Exception:
                    continue

            # Try to capture any data displayed after creating challan
            page_text = await self._read_dprmarks_page_text(page)
            if page_text:
                result["data"] = page_text

        except Exception as e:
            logger.error("DPRMarks Create Challan error: %s", e)

        return result

    async def _read_dprmarks_page_text(self, page: Page) -> Optional[str]:
        """Read text content from DPRMarks portal pages."""
        try:
            content = page.locator("body")
            if await content.is_visible(timeout=2000):
                text = await content.text_content()
                if text and len(text.strip()) > 10:
                    return text.strip()
        except Exception:
            pass
        return None


# ── Popup text parsing ────────────────────────────────────────────────────────


def _parse_popup_text(text: str) -> Optional[dict]:
    """
    Parse a free-text popup from the DP map viewer into a structured dict.
    Common format:
      Zone: Residential Zone (R1)
      Road Width: 18.0 m
      FSI: 1.33
      Reservation: Road
    """
    attrs: dict = {}
    import re

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        m = re.match(
            r"^(Zone|Zone Code|Land Use|Reservation|Road Width|FSI|Height|DP Remark)[:\s]+(.+)$",
            line,
            re.IGNORECASE,
        )
        if m:
            key = m.group(1).strip().upper().replace(" ", "_")
            val = m.group(2).strip()
            attrs[key] = val

    return attrs if attrs else None
