"""
MCGM Property Lookup — Browser Scraper (Playwright)
Automates the MCGM ArcGIS WebApp to search for a property by ward/village/CTS.
Used as the primary fallback when the direct REST API query returns no results.

Key strategy:
  - Intercept ArcGIS /query network responses to capture raw feature JSON
    without relying on fragile DOM scraping.
  - Take a map screenshot after the property is highlighted.
  - Use generous timeouts (60 s initial load) because the MCGM WebApp is a
    complex Esri JS 4.x single-page application.
"""

import asyncio
import base64
import json
import logging
from typing import Optional

from playwright.async_api import (
    Page,
    Request,
    Response,
    async_playwright,
)
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)

MCGM_WEBAPP_URL = (
    "https://mcgm.maps.arcgis.com/apps/webappviewer/index.html"
    "?id=3a5c0a98a75341b985c10700dec6c4b8"
)

# How long to wait for the ArcGIS SPA to fully boot (ms)
APP_LOAD_TIMEOUT = 60_000
# How long to wait for dropdown options to populate after a selection (ms)
DROPDOWN_WAIT_TIMEOUT = 15_000
# How long to wait for the map query network response after clicking Search (ms)
QUERY_RESPONSE_TIMEOUT = 30_000


class MCGMBrowserScraper:
    """Playwright-based scraper for the MCGM CTS property lookup WebApp."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._stealth = Stealth()

    # ── Public API ────────────────────────────────────────────────────────────

    async def scrape(
        self,
        ward: str,
        village: str,
        cts_no: str,
    ) -> dict:
        """Open the MCGM WebApp, navigate the CTS lookup wizard, and return
        structured result dict with keys:
          - feature: raw ArcGIS feature dict (geometry + attributes) or None
          - screenshot_b64: base64 PNG of the map (or None)
          - error: error message string (or None)
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
            page = await context.new_page()
            await self._stealth.apply_stealth_async(page)

            result = await self._run(page, ward, village, cts_no)
            return result

        except Exception as e:
            logger.error("Browser scraper fatal error: %s", e, exc_info=True)
            return {"feature": None, "screenshot_b64": None, "error": str(e)}
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()

    # ── Internal flow ─────────────────────────────────────────────────────────

    async def _run(self, page: Page, ward: str, village: str, cts_no: str) -> dict:
        """Full automation flow. Returns result dict."""

        # ── 1. Intercept ArcGIS feature query responses ────────────────────
        captured_features: list[dict] = []

        async def _on_response(response: Response):
            """Capture any ArcGIS /query response that contains polygon features."""
            url = response.url
            if "/query" not in url.lower():
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                body = await response.json()
            except Exception:
                return
            features = body.get("features", [])
            if not features:
                return
            # Filter for polygon geometry (has 'rings')
            poly_features = [
                f for f in features
                if isinstance(f.get("geometry"), dict)
                and "rings" in f.get("geometry", {})
                and f.get("attributes", {}).get("FP_NO") is not None
            ]
            if poly_features:
                logger.info(
                    "Intercepted ArcGIS query response: %d polygon feature(s) from %s",
                    len(poly_features),
                    url[:120],
                )
                captured_features.extend(poly_features)

        page.on("response", lambda r: asyncio.ensure_future(_on_response(r)))

        # ── 2. Navigate to MCGM WebApp ────────────────────────────────────
        logger.info("Navigating to MCGM WebApp...")
        try:
            await page.goto(MCGM_WEBAPP_URL, timeout=APP_LOAD_TIMEOUT, wait_until="domcontentloaded")
        except Exception as e:
            logger.warning("Navigation did not complete cleanly (continuing): %s", e)

        # Wait for the ArcGIS map container to appear — indicates JS has booted
        try:
            await page.wait_for_selector(
                ".jimu-main-page, #map_root, .esri-view-root, [class*='esri-view']",
                timeout=APP_LOAD_TIMEOUT,
            )
            logger.info("ArcGIS map container detected")
        except Exception:
            logger.warning("Map container selector not found — proceeding anyway")

        # Extra settle time for the SPA to fully initialise widgets
        await asyncio.sleep(8)

        # ── 3. Open the CTS/CS No locate widget ──────────────────────────
        # First check if the Locate Property panel is already open; if not, click its icon
        try:
            panel_icon = page.locator("[title='Locate Property'], .jimu-widget-onscreen-icon:has-text('Locate')")
            if await panel_icon.count() > 0 and not await panel_icon.first.is_visible(timeout=2000):
                await panel_icon.first.click()
                logger.info("Clicked Locate Property icon to open panel")
                await asyncio.sleep(3)
        except Exception:
            pass

        # Debug: log what elements are visible in the task list area
        try:
            task_rows = page.locator("tr, .list-item-name, .task-name-div, [role='button']")
            count = await task_rows.count()
            logger.info("Found %d potential task/button elements in page", count)
            for i in range(min(count, 15)):
                txt = (await task_rows.nth(i).text_content() or "").strip()[:60]
                if txt:
                    logger.info("  Element[%d]: '%s'", i, txt)
        except Exception as e:
            logger.debug("Debug element scan error: %s", e)

        opened = await self._open_cts_widget(page)
        if not opened:
            return {
                "feature": None,
                "screenshot_b64": None,
                "error": "Could not open CTS/CS No locate widget",
            }

        # ── 3b. Click the "Proceed" button on the info/instruction page ──
        try:
            proceed_btn = page.locator("button:has-text('Proceed'), .btn:has-text('Proceed'), input[value='Proceed']").first
            if await proceed_btn.is_visible(timeout=3000):
                await proceed_btn.click()
                logger.info("Clicked 'Proceed' button")
                await asyncio.sleep(3)
            else:
                logger.info("No Proceed button found — form may already be showing")
        except Exception as e:
            logger.debug("Proceed button check: %s", e)

        # ── 4. Select Ward ────────────────────────────────────────────────
        logger.info("Selecting ward: %s", ward)
        ward_selected = await self._select_dropdown_option(
            page, label_text="Ward", option_value=ward
        )
        if not ward_selected:
            # Try partial match for ward too
            ward_selected = await self._select_dropdown_option(
                page, label_text="Ward", option_value=ward, partial=True
            )

        if not ward_selected:
            return {
                "feature": None,
                "screenshot_b64": None,
                "error": f"Could not select ward '{ward}'",
            }

        # Wait for Village dropdown to populate
        await asyncio.sleep(2)

        # ── 5. Select Village ─────────────────────────────────────────────
        logger.info("Selecting village: %s", village)
        village_selected = await self._select_dropdown_option(
            page, label_text="Village", option_value=village
        )
        if not village_selected:
            # Try partial match — village names can differ slightly
            village_selected = await self._select_dropdown_option(
                page, label_text="Village", option_value=village, partial=True
            )
        if not village_selected:
            return {
                "feature": None,
                "screenshot_b64": None,
                "error": f"Could not select village '{village}'",
            }

        # Wait for CTS input to be enabled
        await asyncio.sleep(1)

        # ── 6. Enter CTS No ───────────────────────────────────────────────
        logger.info("Entering CTS No: %s", cts_no)
        cts_entered = await self._enter_cts_no(page, cts_no)
        if not cts_entered:
            return {
                "feature": None,
                "screenshot_b64": None,
                "error": f"Could not enter CTS No '{cts_no}'",
            }

        # ── 7. Click Search ───────────────────────────────────────────────
        logger.info("Clicking Search/Find button...")
        searched = await self._click_search(page)
        if not searched:
            return {
                "feature": None,
                "screenshot_b64": None,
                "error": "Could not click Search button",
            }

        # ── 8. Wait for network response ──────────────────────────────────
        logger.info("Waiting for ArcGIS query response (max %ds)...", QUERY_RESPONSE_TIMEOUT // 1000)
        deadline = QUERY_RESPONSE_TIMEOUT / 1000
        elapsed = 0.0
        poll_interval = 0.5
        while elapsed < deadline and not captured_features:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        feature = None
        if captured_features:
            # Find the feature matching our exact CTS/ward query
            feature = _find_best_match(captured_features, ward, cts_no)
            if not feature:
                feature = captured_features[0]
            logger.info(
                "Feature captured: ward=%s fp_no=%s",
                feature.get("attributes", {}).get("WARD"),
                feature.get("attributes", {}).get("FP_NO"),
            )
        else:
            logger.warning("No polygon features captured from network responses")

        # Extra wait for the map to render the highlight before screenshotting
        await asyncio.sleep(2)

        # ── 9. Screenshot ─────────────────────────────────────────────────
        screenshot_b64 = None
        try:
            png_bytes = await page.screenshot(full_page=False)
            screenshot_b64 = base64.b64encode(png_bytes).decode()
            logger.info("Screenshot captured (%d bytes)", len(png_bytes))
        except Exception as e:
            logger.warning("Screenshot failed: %s", e)

        if feature is None:
            return {
                "feature": None,
                "screenshot_b64": screenshot_b64,
                "error": "Property not found in MCGM ArcGIS database",
            }

        return {"feature": feature, "screenshot_b64": screenshot_b64, "error": None}

    # ── Widget / UI helpers ───────────────────────────────────────────────────

    async def _open_cts_widget(self, page: Page) -> bool:
        """Find and click the 'Locate Land with CTS/CS No' task row.

        The MCGM portal auto-opens a "Locate Property" panel on load.
        Inside it is a task list with rows like:
          - Locate Property with SAC No
          - Locate Land with CTS/CS No  ← we need this one
          - Locate Plot with FP No
        Each row is a <TR role="button"> with class "single-task".
        """
        # Strategy 1: Click the task row containing "CTS" text
        # Use multiple selectors — try click without checking visibility
        selectors_to_try = [
            "tr.single-task:has-text('CTS/CS No')",
            ".task-name-div:has-text('CTS')",
            "text=Locate Land with CTS/CS No",
            "tr:has-text('CTS/CS No')",
            "td:has-text('CTS/CS No')",
        ]
        for sel in selectors_to_try:
            try:
                el = page.locator(sel).first
                count = await el.count() if hasattr(el, 'count') else 1
                if count > 0:
                    await el.click(timeout=5000, force=True)
                    logger.info("Opened CTS widget via selector: %s", sel)
                    await asyncio.sleep(2)
                    return True
            except Exception as e:
                logger.debug("Selector %s failed: %s", sel, str(e)[:60])
                continue

        # Strategy 2: Scan ALL elements for CTS text and force-click
        try:
            rows = page.locator("tr, td, div.list-item-name, [role='button']")
            count = await rows.count()
            for i in range(count):
                row = rows.nth(i)
                txt = (await row.text_content() or "").strip()
                if "CTS/CS No" in txt and len(txt) < 80:
                    await row.click(force=True)
                    logger.info("Opened CTS widget via scan: '%s'", txt[:60])
                    await asyncio.sleep(2)
                    return True
        except Exception as e:
            logger.debug("Row scan failed: %s", e)

        logger.warning("Could not find CTS locate widget")
        return False

    async def _select_dropdown_option(
        self,
        page: Page,
        label_text: str,
        option_value: str,
        partial: bool = False,
    ) -> bool:
        """Find a <select> or custom dropdown labelled `label_text` and choose `option_value`."""
        val_upper = option_value.upper()

        # Try native <select> elements
        select_selectors = [
            f"select[name*='{label_text.lower()}']",
            f"select[id*='{label_text.lower()}']",
            f"label:has-text('{label_text}') + select",
            f"label:has-text('{label_text}') ~ select",
            # Esri/Dojo widget pattern
            f"[data-field*='{label_text.upper()}'] select",
            "select",  # last resort — all selects
        ]

        for sel in select_selectors:
            try:
                elements = page.locator(sel)
                count = await elements.count()
                for i in range(count):
                    el = elements.nth(i)
                    if not await el.is_visible(timeout=1000):
                        continue
                    # Try to find the matching option
                    option_sel = (
                        f"option:has-text('{option_value}')"
                        if not partial
                        else f"option"
                    )
                    opts = el.locator(option_sel)
                    if partial:
                        # Scan all options for partial match
                        opts_count = await opts.count()
                        for j in range(opts_count):
                            opt_text = (await opts.nth(j).text_content() or "").upper()
                            if val_upper in opt_text:
                                opt_val = await opts.nth(j).get_attribute("value") or opt_text
                                await el.select_option(value=opt_val)
                                logger.info(
                                    "Selected '%s' in %s dropdown (partial match '%s')",
                                    opt_text.strip(),
                                    label_text,
                                    option_value,
                                )
                                return True
                    else:
                        if await opts.count() > 0:
                            await el.select_option(label=option_value)
                            logger.info("Selected '%s' in %s dropdown", option_value, label_text)
                            return True
            except Exception:
                continue

        # Fallback: Esri custom dropdown (div-based)
        return await self._select_custom_dropdown(page, label_text, option_value, partial)

    async def _select_custom_dropdown(
        self,
        page: Page,
        label_text: str,
        option_value: str,
        partial: bool = False,
    ) -> bool:
        """Handle Esri/Dojo custom select widgets (div-based dropdowns)."""
        val_upper = option_value.upper()
        # Try to find a container labelled with our field name then click it
        containers = page.locator(
            f"[class*='dijitSelect'], [class*='Select'], [role='listbox'], [role='combobox']"
        )
        count = await containers.count()
        for i in range(count):
            container = containers.nth(i)
            try:
                # Check label nearby
                label = await container.evaluate(
                    "el => el.previousElementSibling ? el.previousElementSibling.textContent : ''"
                )
                if label_text.upper() not in label.upper():
                    continue
                await container.click()
                await asyncio.sleep(0.5)
                # Find option items
                items = page.locator("[class*='dijitMenuItem'], [role='option']")
                items_count = await items.count()
                for j in range(items_count):
                    item = items.nth(j)
                    txt = (await item.text_content() or "").upper()
                    if (partial and val_upper in txt) or (not partial and txt == val_upper):
                        await item.click()
                        logger.info(
                            "Custom dropdown: selected '%s' for %s", txt.strip(), label_text
                        )
                        return True
            except Exception:
                continue
        return False

    async def _enter_cts_no(self, page: Page, cts_no: str) -> bool:
        """Type the CTS number into the input field."""
        input_selectors = [
            "input[placeholder*='CTS']",
            "input[placeholder*='CS No']",
            "input[name*='cts']",
            "input[id*='cts']",
            "input[type='text']",  # last resort
        ]
        for sel in input_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.triple_click()
                    await el.type(cts_no, delay=50)
                    logger.info("Entered CTS No '%s' into input '%s'", cts_no, sel)
                    return True
            except Exception:
                continue
        return False

    async def _click_search(self, page: Page) -> bool:
        """Click the Search/Find/Locate button."""
        button_selectors = [
            "button:has-text('Search')",
            "button:has-text('Find')",
            "button:has-text('Locate')",
            "button:has-text('Go')",
            "input[type='submit']",
            "input[type='button'][value*='Search']",
            "input[type='button'][value*='Find']",
            "[class*='search-btn']",
            "[class*='find-btn']",
            ".btn-primary",
        ]
        for sel in button_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1500):
                    await el.click()
                    logger.info("Clicked search button: %s", sel)
                    return True
            except Exception:
                continue

        # Last resort: press Enter in the CTS input
        try:
            await page.keyboard.press("Enter")
            logger.info("Pressed Enter as search fallback")
            return True
        except Exception:
            pass

        return False


# ── Helpers ───────────────────────────────────────────────────────────────────


def _find_best_match(features: list[dict], ward: str, cts_no: str) -> Optional[dict]:
    """Return the feature whose attributes best match the requested ward/cts_no."""
    ward_upper = ward.upper()
    cts_upper = cts_no.upper()
    for f in features:
        attrs = f.get("attributes", {})
        if (
            str(attrs.get("WARD", "")).upper() == ward_upper
            and str(attrs.get("FP_NO", "")).upper() == cts_upper
        ):
            return f
    # Looser match — just CTS/FP_NO
    for f in features:
        attrs = f.get("attributes", {})
        if str(attrs.get("FP_NO", "")).upper() == cts_upper:
            return f
    return None
