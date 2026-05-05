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
import logging

from playwright.async_api import (
    Page,
    Response,
    async_playwright,
)
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)

MCGM_WEBAPP_URL = (
    "https://mcgm.maps.arcgis.com/apps/webappviewer/index.html?id=3a5c0a98a75341b985c10700dec6c4b8"
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
        tps_name: str | None = None,
        use_fp: bool = False,
    ) -> dict:
        """Open the MCGM WebApp, navigate the property lookup wizard, and return
        structured result dict with keys:
          - feature: raw ArcGIS feature dict (geometry + attributes) or None
          - screenshot_b64: base64 PNG of the map (or None)
          - error: error message string (or None)

        Args:
            ward: Ward code (e.g. "K/W")
            village: Village name (for CTS mode)
            cts_no: CTS or FP number
            tps_name: TPS scheme name (for FP mode, e.g. "VILE PARLE")
            use_fp: If True, use "Locate Plot with FP No" widget
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
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            await self._stealth.apply_stealth_async(page)

            return await self._run(page, ward, village, cts_no, tps_name, use_fp)

        except Exception as e:
            logger.error("Browser scraper fatal error: %s", e, exc_info=True)
            return {"feature": None, "screenshot_b64": None, "error": str(e)}
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()

    # ── Internal flow ─────────────────────────────────────────────────────────

    async def _run(
        self,
        page: Page,
        ward: str,
        village: str,
        cts_no: str,
        tps_name: str | None = None,
        use_fp: bool = False,
    ) -> dict:
        """Full automation flow. Returns result dict.

        Args:
            village: Village name (for CTS mode)
            tps_name: TPS scheme name (for FP mode)
            use_fp: If True, use FP widget; otherwise use CTS widget
        """
        # For FP mode, use TPS instead of village
        effective_village = tps_name if use_fp else village

        # Building data from popup
        building_data = {}

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
                f
                for f in features
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
            await page.goto(
                MCGM_WEBAPP_URL, timeout=APP_LOAD_TIMEOUT, wait_until="domcontentloaded"
            )
        except Exception as e:
            logger.warning("Navigation did not complete cleanly (continuing): %s", e)

        # Wait for the ArcGIS map container to appear — indicates JS has booted
        try:
            await page.wait_for_selector(
                ".jimu-main-page, #map_root, .esri-view-root, [class*='esri-view']",
                timeout=APP_LOAD_TIMEOUT,
            )
            logger.info("ArcGIS map container detected")

            # ── 2a. Dismiss Splash Screen/Disclaimer ──────────────────────
            # This appears as an overlay with a "Proceed" or "OK" button
            try:
                proceed_btn = page.locator(
                    "button:has-text('Proceed'), .btn:has-text('Proceed'), input[value='Proceed']"
                ).first
                if await proceed_btn.is_visible(timeout=5000):
                    await proceed_btn.click()
                    logger.info("Dismissed splash screen/disclaimer")
                    await asyncio.sleep(2)
            except Exception:
                pass

        except Exception:
            logger.warning("Map container selector not found — proceeding anyway")

        # Extra settle time for the SPA to fully initialise widgets
        await asyncio.sleep(8)

        # ── 3. Open the CTS/CS No locate widget ──────────────────────────
        # First check if the Locate Property panel is already open; if not, click its icon
        try:
            panel_icon = page.locator(
                "[title='Locate Property'], .jimu-widget-onscreen-icon:has-text('Locate')"
            )
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

        # ── 3a. Debug: dump page structure ────────────────────────────────────
        try:
            body_html = await page.content()
            body_len = len(body_html)
            logger.info("Page HTML length: %d bytes", body_len)
            # Check for key elements
            has_map = await page.locator(".jimu-map, #map_root, [class*='esri']").count()
            has_widgets = await page.locator("[class*='widget']").count()
            logger.info("Map elements: %d, Widget elements: %d", has_map, has_widgets)
        except Exception as e:
            logger.debug("Debug dump failed: %s", str(e)[:100])

        opened = await self._open_property_widget(page, use_fp=use_fp)
        if not opened:
            # Try CTS widget as last resort
            if not use_fp:
                opened = await self._open_cts_widget(page)

            if not opened:
                return {
                    "feature": None,
                    "screenshot_b64": None,
                    "error": "Could not open property locate widget",
                }

        # Extra wait for widget form to settle
        await asyncio.sleep(2)

        # ── 4. Select Ward ────────────────────────────────────────────────
        logger.info("Selecting ward: %s", ward)
        ward_selected = await self._select_dropdown_option(
            page, label_text="Ward", option_value=ward
        )
        if not ward_selected:
            # Quick fallback: directly fill the first visible input matching "ward"
            ward_selected = await self._fill_form_input(page, "Ward", ward)
        if not ward_selected:
            logger.warning("Ward selection failed, trying to continue anyway...")

        await asyncio.sleep(1)

        # ── 5. Select Village or TPS ───────────────────────────────────────
        # For FP mode: use TPS dropdown instead of Village
        dropdown_label = "TPS" if use_fp else "Village"
        logger.info("Selecting %s: %s", dropdown_label, effective_village)
        village_selected = await self._select_dropdown_option(
            page, label_text=dropdown_label, option_value=effective_village
        )
        if not village_selected:
            village_selected = await self._fill_form_input(page, dropdown_label, effective_village)
        if not village_selected:
            logger.warning("%s selection failed, trying to continue anyway...", dropdown_label)

        await asyncio.sleep(1)

        # ── 6. Enter CTS/FP No ───────────────────────────────────────────
        logger.info("Entering property No: %s (FP=%s)", cts_no, use_fp)
        cts_entered = await self._enter_cts_no(page, cts_no, use_fp=use_fp)
        if not cts_entered:
            cts_entered = await self._fill_form_input(page, "CTS", cts_no)
        if not cts_entered:
            return {
                "feature": None,
                "screenshot_b64": None,
                "error": f"Could not enter property No '{cts_no}'",
            }

        # ── 7. Click Search ───────────────────────────────────────────
        logger.info("Clicking Search/Find button...")
        searched = await self._click_search(page)
        if not searched:
            # Keyboard fallback
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)
            searched = True
        if not searched:
            return {
                "feature": None,
                "screenshot_b64": None,
                "error": "Could not click Search button",
            }

        # After Search, wait for building details popup and ArcGIS network response.
        # NOTE: the portal shows a Ward confirmation dropdown after Search (not a Village
        # dropdown) — the second village-selection block that was here was incorrectly
        # trying to select the village name from ward codes (A/B/G/S...).
        await asyncio.sleep(3)
        building_data = await self._get_building_details(page)

        # ── 8. Wait for network response ──────────────────────────────────
        logger.info(
            "Waiting for ArcGIS query response (max %ds)...", QUERY_RESPONSE_TIMEOUT // 1000
        )
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
                "building_data": building_data,
                "error": "Property not found in MCGM ArcGIS database",
            }

        return {
            "feature": feature,
            "screenshot_b64": screenshot_b64,
            "building_data": building_data,
            "error": None,
        }

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
                count = await el.count() if hasattr(el, "count") else 1
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
            logger.debug("Row scan failed: %s", str(e)[:60])

        logger.warning("Could not find CTS locate widget")
        return False

    async def _open_property_widget(self, page: Page, use_fp: bool = False) -> bool:
        """Open the appropriate property locate widget.

        Args:
            use_fp: If True, click "Locate Plot with FP No"; otherwise "Locate Land with CTS/CS No"
        """
        widget_type = "FP" if use_fp else "CTS/CS"

        # Selectors for each widget type
        if use_fp:
            selectors = [
                "tr.single-task:has-text('FP')",
                ".task-name-div:has-text('FP')",
                "text=Locate Plot with FP No",
                "text=Locate via FP",
                "text=Locate via CTS or FP",
                "tr:has-text('FP')",
                "td:has-text('FP')",
            ]
        else:
            selectors = [
                "tr.single-task:has-text('CTS')",
                ".task-name-div:has-text('CTS')",
                "text=Locate Land with CTS/CS No",
                "text=Locate via CTS",
                "text=Locate via CTS or FP",
                "tr:has-text('CTS')",
                "td:has-text('CTS')",
            ]

        for sel in selectors:
            try:
                el = page.locator(sel).first
                count = await el.count() if hasattr(el, "count") else 1
                if count > 0:
                    await el.click(timeout=5000, force=True)
                    logger.info("Opened %s widget via: %s", widget_type, sel)
                    await asyncio.sleep(2)
                    return True
            except Exception as e:
                logger.debug("Selector %s failed: %s", sel, str(e)[:60])
                continue

        # Fallback: scan all elements
        search_text = "FP" if use_fp else "CTS"
        try:
            rows = page.locator("tr, td, div.list-item-name, [role='button']")
            count = await rows.count()
            for i in range(count):
                row = rows.nth(i)
                txt = (await row.text_content() or "").strip()
                if search_text in txt and len(txt) < 80:
                    await row.click(force=True)
                    logger.info("Opened %s widget via scan: %s", widget_type, txt[:60])
                    await asyncio.sleep(2)
                    return True
        except Exception as e:
            logger.debug("Row scan failed: %s", str(e)[:60])

        logger.warning("Could not find %s locate widget", widget_type)
        return False

    async def _select_dropdown_option(
        self,
        page: Page,
        label_text: str,
        option_value: str,
        partial: bool = False,
    ) -> bool:
        """Find a <select> or custom dropdown labelled `label_text` and choose `option_value`.
        Uses JavaScript injection for direct, fast selection."""
        val_upper = option_value.upper()

        # Strategy 1: JavaScript injection - find and set the value directly
        try:
            result = await page.evaluate(
                """(label) => {
                const labels = document.querySelectorAll('label, span, div');
                for (let l of labels) {
                    if (l.textContent && l.textContent.toUpperCase().includes(label.toUpperCase())) {
                        // Look for associated select/input nearby
                        let next = l.nextElementSibling;
                        while (next) {
                            if (next.tagName === 'SELECT') {
                                // Found a select - try to find matching option
                                const opts = next.options;
                                for (let i = 0; i < opts.length; i++) {
                                    const txt = opts[i].textContent.toUpperCase();
                                    const val = opts[i].value;
                                    if (txt.includes(label.toUpperCase()) || label.toUpperCase().includes(txt)) {
                                        next.selectedIndex = i;
                                        next.dispatchEvent(new Event('change'));
                                        return { success: true, method: 'select', value: val };
                                    }
                                }
                            }
                            // Check for dijit/form input
                            if (next.tagName === 'INPUT' || next.classList.contains('dijit')) {
                                next.value = label;
                                next.dispatchEvent(new Event('change'));
                                return { success: true, method: 'input', value: label };
                            }
                            next = next.nextElementSibling;
                        }
                    }
                }
                return { success: false };
            }""",
                option_value,
            )

            if result and result.get("success"):
                logger.info(
                    "JavaScript selected %s in %s dropdown: %s", option_value, label_text, result
                )
                return True
        except Exception as e:
            logger.debug("JS dropdown selection failed: %s", str(e)[:80])

        # Strategy 2: Try ArcGIS checkBtn index-based selection (stable for this UI)
        try:
            # Map labels to their consistent indexes in the "Locate Property" widget
            label_indexes = {"Ward": 0, "Village": 1, "TPS": 1, "CTS": 2}
            idx = label_indexes.get(label_text)
            if idx is not None:
                # Find all checkBtn elements in the LocateProperty widget
                dropdowns = page.locator(".jimu-widget-custom-widget-LocateProperty .checkBtn")
                if await dropdowns.count() > idx:
                    trigger = dropdowns.nth(idx)
                    await trigger.click()
                    logger.info("Clicked %s dropdown (index %d)", label_text, idx)
                    await asyncio.sleep(2)

                    # Try to find the item in the popup
                    # Dojo popups are often at the end of the body
                    item_selector = f"div.item:has-text('{option_value}')"
                    item = page.locator(item_selector).first

                    # If not visible, try typing in any visible input inside the widget
                    if not await item.is_visible(timeout=1000):
                        inputs = page.locator(".jimu-widget-custom-widget-LocateProperty input")
                        if await inputs.count() > 0:
                            # Usually the last clicked dropdown focuses the relevant input
                            await page.keyboard.type(option_value, delay=50)
                            await asyncio.sleep(2)

                    # Click the matching item
                    item = page.locator(item_selector).first
                    if await item.is_visible(timeout=3000):
                        await item.click()
                        logger.info("Selected %s via index %d + text match", option_value, idx)
                        return True

                    # Last resort: press Enter
                    await page.keyboard.press("Enter")
                    logger.info("Selected %s via index %d + Enter fallback", option_value, idx)
                    return True
        except Exception as e:
            logger.debug("Index-based checkBtn failed: %s", str(e)[:60])

        # Strategy 3: Try dijit form fields directly by common IDs (from ArcGIS portal)
        field_map = {
            "Ward": "SelectWardR",
            "Village": "SelectVillageR",
            "TPS": "SelectVillageR",
            "CTS": "SelectCTSR",
        }
        field_id = field_map.get(label_text, f"Select{label_text}R")

        try:
            dijit_input = page.locator(f"input[id='{field_id}']").first
            if await dijit_input.is_visible(timeout=2000):
                await dijit_input.click()
                await asyncio.sleep(0.5)
                await dijit_input.fill(option_value)
                await asyncio.sleep(1)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                logger.info("Selected %s via dijit field %s", option_value, field_id)
                return True
        except Exception as e:
            logger.debug("Dijit field %s failed: %s", field_id, str(e)[:60])

        # Strategy 3: Try native select elements
        select_selectors = ["select"]

        for sel in select_selectors:
            try:
                elements = page.locator(sel)
                count = await elements.count()
                for i in range(count):
                    el = elements.nth(i)
                    if not await el.is_visible(timeout=500):
                        continue
                    all_opts = el.locator("option")
                    opts_count = await all_opts.count()
                    for j in range(opts_count):
                        opt_text = (await all_opts.nth(j).text_content() or "").strip()
                        if opt_text.upper() == val_upper or (
                            partial and val_upper in opt_text.upper()
                        ):
                            opt_val = await all_opts.nth(j).get_attribute("value") or opt_text
                            await el.select_option(value=opt_val)
                            logger.info("Selected '%s' via native select", opt_text)
                            return True
            except Exception:
                continue

        # Fallback: Esri custom dropdown
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

        # More aggressive approach: look for any dropdown-like elements near the label
        all_containers = page.locator(
            "[class*='dijit'], [role='listbox'], [role='combobox'], .dijitSelect"
        )
        count = await all_containers.count()
        logger.debug("Found %d potential dropdown containers", count)

        # Try finding the dropdown by clicking near the label
        for i in range(count):
            container = all_containers.nth(i)
            try:
                if not await container.is_visible(timeout=500):
                    continue
                # Check if there's a label nearby
                prev = await container.evaluate("""el => {
                    let prev = el.previousElementSibling;
                    while (prev) {
                        if (prev.offsetParent !== null) return prev.textContent;
                        prev = prev.previousElementSibling;
                    }
                    return '';
                }""")
                if prev and label_text.upper() in prev.upper():
                    # This is our dropdown - click it to open options
                    await container.click()
                    await asyncio.sleep(1)
                    # Now find the option in the popup menu
                    menu_items = page.locator(
                        "[class*='dijitMenuItem'], [role='option'], .dijitMenuItem"
                    )
                    items_count = await menu_items.count()
                    for j in range(items_count):
                        item = menu_items.nth(j)
                        txt = (await item.text_content() or "").strip()
                        if txt:
                            txt_upper = txt.upper()
                            match = (partial and val_upper in txt_upper) or (
                                not partial and txt_upper == val_upper
                            )
                            if match:
                                await item.click()
                                logger.info(
                                    "Custom dropdown: selected '%s' for %s", txt, label_text
                                )
                                return True
            except Exception as e:
                logger.debug("Container %d failed: %s", i, str(e)[:60])
                continue

        # Try finding by clicking the visible text of the dropdown (the "button" part)
        try:
            buttons = page.locator(".dijitButtonNode, .dijitDropDownButton")
            btn_count = await buttons.count()
            for i in range(btn_count):
                btn = buttons.nth(i)
                txt = await btn.text_content()
                if txt and label_text.upper() in txt.upper():
                    await btn.click()
                    await asyncio.sleep(1)
                    # Look for option in menu
                    items = page.locator("[class*='MenuItem']")
                    for j in range(await items.count()):
                        opt = items.nth(j)
                        opt_txt = (await opt.text_content() or "").strip()
                        if opt_txt:
                            opt_upper = opt_txt.upper()
                            match = (partial and val_upper in opt_upper) or (
                                not partial and opt_upper == val_upper
                            )
                            if match:
                                await opt.click()
                                logger.info(
                                    "Selected via dropdown button: %s for %s", opt_txt, label_text
                                )
                                return True
        except Exception as e:
            logger.debug("Dropdown button approach failed: %s", str(e)[:60])

        return False

    async def _enter_cts_no(self, page: Page, cts_no: str, use_fp: bool = False) -> bool:
        """Type the CTS or FP number into the input field.

        Args:
            cts_no: The CTS or FP number to enter
            use_fp: If True, this is an FP number (VI/18 format)
        """
        input_selectors = [
            ".jimu-widget-custom-widget-LocateProperty input[placeholder*='CTS']",
            ".jimu-widget-custom-widget-LocateProperty input[placeholder*='CS No']",
            ".jimu-widget-custom-widget-LocateProperty input[placeholder*='FP']",
            ".jimu-widget-custom-widget-LocateProperty input[id*='SelectCTSR']",
            "input[placeholder*='CTS']",
            "input[id*='SelectCTSR']",
            "input[type='text']:not(.arcgisSearch input)",
        ]

        for sel in input_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.clear()
                    await el.fill(cts_no)
                    await asyncio.sleep(0.5)
                    await el.press("Tab")
                    logger.info("Entered property No '%s' via selector '%s'", cts_no, sel)
                    return True
            except Exception as e:
                logger.debug("Selector %s failed: %s", sel, str(e)[:50])
                continue

        # Try with JavaScript - find any visible input in the form
        try:
            result = await page.evaluate(
                """(val) => {
                // Find all text inputs that are visible
                const inputs = document.querySelectorAll('input[type="text"], input[dijit="TextBox"]');
                for (let inp of inputs) {
                    // Check if visible (has size and not hidden)
                    if (inp.offsetParent !== null && inp.style.display !== 'none') {
                        // Also check parent containers
                        let parent = inp.parentElement;
                        while (parent) {
                            if (parent.style && parent.style.display === 'none') break;
                            parent = parent.parentElement;
                        }
                        inp.value = val;
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                        return inp.id || inp.name;
                    }
                }
                return null;
            }""",
                cts_no,
            )
            if result:
                logger.info("Entered property No via JS: '%s' (field: %s)", cts_no, result)
                return True
        except Exception as e:
            logger.debug("JS fallback failed: %s", str(e)[:50])

        logger.warning("Could not enter property No '%s'", cts_no)
        return False

    async def _click_search(self, page: Page) -> bool:
        """Click the Search or Apply button."""
        button_selectors = [
            ".jimu-widget-custom-widget-LocateProperty .apply-btn",
            ".jimu-widget-custom-widget-LocateProperty button:has-text('Apply')",
            ".jimu-widget-custom-widget-LocateProperty .btn:has-text('Apply')",
            "button:has-text('Apply')",
            "button:has-text('Search')",
            "input[type='button'][value='Apply']",
            "input[type='button'][value='Search']",
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

    async def _fill_form_input(self, page: Page, field_label: str, value: str) -> bool:
        """Direct form input filling as fallback."""
        field_ids = {
            "Ward": ["SelectWardR", "wardInput"],
            "Village": ["SelectVillageR", "villageInput"],
            "CTS": ["SelectCTSR", "ctsInput", "ctsNo"],
        }
        ids = field_ids.get(field_label, [])

        for fid in ids:
            try:
                inp = page.locator(f"input[id='{fid}'], input[name='{fid}'], #{fid}").first
                if await inp.is_visible(timeout=1000):
                    await inp.fill(value)
                    logger.info("Filled %s via input#%s", value, fid)
                    return True
            except Exception:
                continue
        return False

    async def _get_building_details(self, page: Page) -> dict:
        """Click Apply button and extract building details from popup.

        After filling the form, click Apply to see building info popup.
        Then click arrows (carousel) to get more details like floors, height, etc.
        """
        building_data = {}

        # Click Apply button - try more selectors
        apply_selectors = [
            "button:has-text('Apply')",
            "input[value='Apply']",
            "button.btn-primary",
            "#btnApply",
            "[id*='Apply']",
        ]

        clicked_apply = False
        for sel in apply_selectors:
            try:
                btn = page.locator(sel)
                if await btn.count() > 0 and await btn.first.is_visible(timeout=2000):
                    await btn.first.click()
                    logger.info("Clicked Apply button via: %s", sel)
                    clicked_apply = True
                    break
            except Exception as e:
                logger.debug("Apply selector %s failed: %s", sel, str(e)[:50])
                continue

        if not clicked_apply:
            logger.warning("Could not click Apply button")
            return building_data

        # Wait a bit for popup to appear
        await asyncio.sleep(2)

        # Try to capture popup/building info
        try:
            # Take screenshot to see what's on screen
            png = await page.screenshot()
            logger.info("Screenshot captured after Apply click (%d bytes)", len(png))

            # Look for any visible popup or info panel
            body_text = await page.locator("body").text_content()
            if body_text and len(body_text) > 100:
                building_data["page_text"] = body_text[:3000]
                logger.info("Page text length after Apply: %d chars", len(body_text))

            # Look for any modal/popup
            modal_selectors = [
                ".modal",
                ".popup",
                "[class*='modal']",
                "[class*='popup']",
                ".esri-popup",
                "[role='dialog']",
            ]

            for sel in modal_selectors:
                try:
                    modal = page.locator(sel)
                    if await modal.count() > 0:
                        for i in range(await modal.count()):
                            if await modal.nth(i).is_visible(timeout=1000):
                                text = await modal.nth(i).text_content()
                                if text and len(text) > 20:
                                    building_data[f"modal_{sel}"] = text[:1000]
                                    logger.info("Found modal content via %s: %s", sel, text[:200])
                except Exception:
                    continue

            # Click any navigation arrows in popup
            nav_selectors = [
                "button >> nth=0",
                "[class*='arrow']",
                ".esri-popup__navigation",
            ]

            for sel in nav_selectors:
                try:
                    nav = page.locator(sel)
                    if await nav.count() > 0:
                        for i in range(min(await nav.count(), 3)):
                            await nav.nth(i).click()
                            await asyncio.sleep(1)
                            logger.info("Clicked navigation %d", i)
                except Exception:
                    continue

        except Exception as e:
            logger.warning("Error capturing building details: %s", str(e)[:100])

        return building_data

    async def _extract_building_details_from_popup(self, page: Page) -> dict:
        """Extract structured building details from popup content."""
        details = {}

        try:
            # Look for common building info labels
            labels = [
                "Building Name",
                "Building Type",
                "Construction Type",
                "Floors",
                "Height",
                "SAC Number",
                "Address",
            ]

            for label in labels:
                # Try to find label + value pairs
                selectors = [
                    f"text={label}:near(text)",
                    f"span:has-text('{label}')",
                    f"div:has-text('{label}')",
                ]
                for sel in selectors:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=1000):
                            parent = el.locator("xpath=..")
                            value_el = parent.locator("span, div, label").nth(1)
                            if await value_el.is_visible(timeout=500):
                                value = await value_el.text_content()
                                if value:
                                    key = label.lower().replace(" ", "_")
                                    details[key] = value.strip()
                    except Exception:
                        continue

        except Exception as e:
            logger.debug("Extraction failed: %s", str(e)[:50])

        return details


# ── Helpers ───────────────────────────────────────────────────────────────────


def _find_best_match(features: list[dict], ward: str, cts_no: str) -> dict | None:
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
