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
import datetime
import logging
from pathlib import Path

from playwright.async_api import Page, Response, async_playwright

logger = logging.getLogger(__name__)

# DP 2034 public map
DP_MAP_URL = "https://mcgmapp.mcgm.gov.in/DP2034/"

# DPRMarks portal (requires login)
DPREMARKS_URL = "https://dpremarks.mcgm.gov.in/dp2034/"

# Fallback: MCGM ArcGIS portal main app (has DP layer)
MCGM_ARCGIS_URL = (
    "https://mcgm.maps.arcgis.com/apps/webappviewer/index.html?id=3a5c0a98a75341b985c10700dec6c4b8"
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
        lat: float | None = None,
        lng: float | None = None,
        use_fp_scheme: bool = False,
        tps_scheme: str | None = None,
        fp_no: str | None = None,
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
                ignore_https_errors=True,
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

            result = await self._run(page, ward, village, cts_no, lat, lng, use_fp_scheme, tps_scheme, fp_no)
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
        lat: float | None,
        lng: float | None,
        use_fp_scheme: bool = False,
        tps_scheme: str | None = None,
        fp_no: str | None = None,
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

        from ..core import settings as _settings

        # When DPRMarks credentials are configured, skip the public map tiers
        # and go straight to the official portal — it's the authoritative source.
        if _settings.DPRMARKS_USERNAME and _settings.DPRMARKS_PASSWORD:
            logger.info("DPRMarks credentials set — going direct to DPRMarks portal")
            return await self._try_dprmarks_portal(page, ward, village, cts_no, lat, lng, captured_data, use_fp_scheme=use_fp_scheme, tps_scheme=tps_scheme, fp_no=fp_no)

        # ── 2. Try the DP 2034 public map first ───────────────────────────
        logger.info("Navigating to MCGM DP 2034 map...")
        result = await self._try_dp_map(page, ward, village, cts_no, lat, lng, captured_data)
        if result.get("attributes") or result.get("screenshot_b64"):
            return result

        # ── 3. Fallback: MCGM ArcGIS WebApp ──────────────────────────────
        logger.info("Falling back to MCGM ArcGIS WebApp...")
        result = await self._try_arcgis_webapp(page, ward, village, cts_no, lat, lng, captured_data)
        if result.get("attributes") or result.get("screenshot_b64"):
            return result

        # ── 4. Fallback: DPRMarks portal ─────────────────────────────────
        logger.info("Falling back to DPRMarks portal...")
        return await self._try_dprmarks_portal(page, ward, village, cts_no, lat, lng, captured_data, use_fp_scheme=use_fp_scheme, tps_scheme=tps_scheme, fp_no=fp_no)

    async def _try_dp_map(
        self,
        page: Page,
        ward: str,
        village: str,
        cts_no: str,
        lat: float | None,
        lng: float | None,
        captured_data: list,
    ) -> dict:
        """Navigate the MCGM DP 2034 public viewer."""
        try:
            await page.goto(DP_MAP_URL, timeout=APP_LOAD_TIMEOUT, wait_until="domcontentloaded")
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
        lat: float | None,
        lng: float | None,
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

    async def _try_cts_search(self, page: Page, ward: str, village: str, cts_no: str) -> bool:
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
                    await el.click(click_count=3)
                    await el.type(f"{ward} {cts_no}", delay=50)
                    await page.keyboard.press("Enter")
                    logger.info("Searched for CTS in DP map via selector: %s", sel)
                    return True
            except Exception:
                continue
        return False

    async def _read_popup_text(self, page: Page) -> str | None:
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

    async def _screenshot(self, page: Page) -> str | None:
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
        lat: float | None,
        lng: float | None,
        captured_data: list,
        use_fp_scheme: bool = False,
        tps_scheme: str | None = None,
        fp_no: str | None = None,
    ) -> dict:
        """
        Navigate the DPRMarks portal (https://dpremarks.mcgm.gov.in/dp2034/)
        Workflow: login -> Report button -> ward/village/CTS -> next -> next -> create challan
        Falls back to FP path (ward/TPS scheme/FP number) if CTS is not in dropdown.
        """

        try:
            await page.goto(DPREMARKS_URL, timeout=APP_LOAD_TIMEOUT, wait_until="domcontentloaded")
            logger.info("Navigated to DPRMarks portal: %s", page.url)
        except Exception as e:
            logger.warning("DPRMarks portal navigation failed: %s", e)
            return {"attributes": None, "screenshot_b64": None, "error": str(e)}

        await asyncio.sleep(5)

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

        # ── Step 3 & 4: Fill form and proceed ──────────────────────────────────
        # Strategy: try CTS path first (unless use_fp_scheme=True).
        # If generateChallan doesn't become enabled after generateCTSreport,
        # the CTS number is not in the portal's dropdown — fall back to FP path.
        fp_no_for_form = fp_no or cts_no  # if no explicit fp_no, try cts_no as FP

        if not use_fp_scheme:
            # CTS path: SelectWardR → SelectVillageR → SelectCTSR → generateCTSreport
            fill_ok = await self._dprmarks_fill_form(page, ward, village, cts_no)
            next_ok = False
            if fill_ok:
                next_ok = await self._dprmarks_click_next(page, path="cts")
                if next_ok:
                    logger.info("CTS path succeeded — proceeding to challan")
                    use_fp_scheme = False  # stay on CTS path
            
            if not fill_ok or not next_ok:
                logger.warning("CTS path failed (fill or next) — trying FP path")
                use_fp_scheme = True  # fall back to FP path
                logger.info("Switching to FP tab on the current form...")
                await asyncio.sleep(1)

        if use_fp_scheme:
            # FP path: SelectWardR → SelectVillageR → SelectTPSSchemeR → SelectFPR → generateFPreport
            if False and not tps_scheme:
                logger.error("FP path required but no tps_scheme provided — cannot proceed")
                return {
                    "attributes": None,
                    "screenshot_b64": await self._screenshot(page),
                    "error": "CTS not in portal dropdown and no tps_scheme provided for FP fallback",
                }
            fill_ok = await self._dprmarks_fill_form_fp(page, ward, village, tps_scheme, fp_no_for_form)
            if not fill_ok:
                return {
                    "attributes": None,
                    "screenshot_b64": await self._screenshot(page),
                    "error": "Failed to fill FP form fields",
                }
            next_ok = await self._dprmarks_click_next(page, path="fp", ward=ward, village=village, tps_scheme=tps_scheme, fp_no=fp_no_for_form)
            if not next_ok:
                return {
                    "attributes": None,
                    "screenshot_b64": await self._screenshot(page),
                    "error": "Failed to proceed through FP Next steps",
                }

        # ── Step 5: Click 'Create Challan' → capture bank selection popup ────
        # After generateChallan loads the challan summary, 'Create Challan' opens
        # a popup with Indian Bank / Maharashtra Bank / Citi Bank options.
        bank_popup_page = await self._dprmarks_click_challan_capture_popup(page)
        if bank_popup_page is None:
            return {
                "attributes": None,
                "screenshot_b64": await self._screenshot(page),
                "error": "Bank selection popup did not open after 'Create Challan'",
            }
        logger.info("Bank selection page ready: %s", bank_popup_page.url)

        # ── Step 6: Pay (or skip) and download PDF ───────────────────────────
        import uuid as _uuid

        from ..core import settings
        from .ccavenue_payer import CCAvenuePayer
        from .payment_queue import PaymentQueue
        job_id = str(_uuid.uuid4())
        pdf_bytes = None
        payment_status = "failed"
        payment_transaction_id = None
        payment_paid_at = None

        if settings.SKIP_PAYMENT:
            logger.info("SKIP_PAYMENT=true — using test PDF")
            pdf_bytes = self._load_test_pdf()
            payment_status = "skipped"
        else:
            payment_queue = PaymentQueue(redis_url=settings.REDIS_URL)
            try:
                async with payment_queue.session(
                    job_id,
                    wait_seconds=settings.PAYMENT_QUEUE_WAIT_SECONDS,
                ):
                    payer = CCAvenuePayer(
                        timeout_seconds=settings.PAYMENT_TIMEOUT_SECONDS,
                    )
                    # bank_popup_page IS the bank selection page — pass it directly
                    # Use wallet payment method if configured, otherwise UPI
                    payment_method = getattr(settings, "PAYMENT_METHOD", "upi")
                    if payment_method == "wallet":
                        wallet_type = getattr(settings, "WALLET_TYPE", "phonepe")
                        result = await payer.pay(
                            bank_popup_page,
                            payment_method="wallet",
                            wallet_type=wallet_type,
                        )
                    else:
                        result = await payer.pay(
                            bank_popup_page,
                            upi_vpa=settings.BUSINESS_UPI_VPA,
                        )

                    if result.timed_out:
                        return {
                            "attributes": None,
                            "screenshot_b64": await self._screenshot(page),
                            "error": "payment_timeout",
                            "payment_transaction_id": None,
                            "payment_status": "failed",
                            "payment_amount": 4700.00,
                            "payment_paid_at": None,
                        }
                    if not result.success:
                        return {
                            "attributes": None,
                            "screenshot_b64": await self._screenshot(page),
                            "error": f"payment_failed: {result.error}",
                            "payment_transaction_id": None,
                            "payment_status": "failed",
                            "payment_amount": 4700.00,
                            "payment_paid_at": None,
                        }

                    payment_transaction_id = result.transaction_id
                    payment_paid_at = datetime.datetime.utcnow().isoformat()
                    payment_status = "paid"
                    logger.info("Payment confirmed — txn_id=%s", payment_transaction_id)
                    pdf_bytes = await self._download_report_pdf(page)
            except RuntimeError as e:
                return {
                    "attributes": None,
                    "screenshot_b64": None,
                    "error": f"payment_queue_timeout: {e}",
                    "payment_transaction_id": None,
                    "payment_status": "failed",
                    "payment_amount": 4700.00,
                    "payment_paid_at": None,
                }
            finally:
                await payment_queue.close()

        if not pdf_bytes:
            return {
                "attributes": None,
                "screenshot_b64": await self._screenshot(page),
                "error": "pdf_download_failed",
                "payment_transaction_id": None,
                "payment_status": payment_status,
                "payment_amount": 4700.00,
                "payment_paid_at": None,
            }

        from .dp_pdf_parser import parse_dp_pdf
        parsed = parse_dp_pdf(pdf_bytes)

        return {
            "attributes": parsed,
            "screenshot_b64": await self._screenshot(page),
            "error": None,
            "pdf_bytes": pdf_bytes,
            "payment_status": payment_status,
            "payment_transaction_id": payment_transaction_id,
            "payment_amount": 4700.00,
            "payment_paid_at": None if settings.SKIP_PAYMENT else payment_paid_at,
        }

    async def _dprmarks_login(self, page: Page) -> bool:
        """Login to DPRMarks portal with credentials from settings."""
        from ..core import settings

        username = settings.DPRMARKS_USERNAME
        password = settings.DPRMARKS_PASSWORD

        if not username or not password:
            logger.warning("DPRMarks credentials not configured")
            return False

        try:
            # Dump page text for diagnosis
            try:
                body = await page.evaluate(
                    "() => document.body ? document.body.innerText.substring(0, 600) : 'no body'"
                )
                logger.info("Page text before login: %s", body)
            except Exception:
                pass

            # Step 1: Open the login form — try multiple approaches
            # First check if userID is already visible (form already open)
            try:
                already_visible = await page.locator("input[id='userID']").first.is_visible(timeout=2_000)
            except Exception:
                already_visible = False

            if not already_visible:
                # Try clicking the login link via several selectors
                login_selectors = [
                    "a[id='user_login']",
                    "#user_login",
                    "a:has-text('Login')",
                    "a:has-text('Sign In')",
                    "button:has-text('Login')",
                    "[onclick*='login']",
                ]
                clicked_login = False
                for sel in login_selectors:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=2_000):
                            await el.click()
                            logger.info("Clicked login link via selector: %s", sel)
                            clicked_login = True
                            break
                    except Exception:
                        continue

                if not clicked_login:
                    # JS fallback — try common IDs/functions
                    await page.evaluate("""() => {
                        var ids = ['user_login','loginLink','login','loginBtn'];
                        for (var i=0; i<ids.length; i++) {
                            var el = document.getElementById(ids[i]);
                            if (el) { el.click(); return ids[i]; }
                        }
                        // Try any link with "login" text
                        var links = document.querySelectorAll('a,button');
                        for (var j=0; j<links.length; j++) {
                            if ((links[j].innerText||'').toLowerCase().includes('login')) {
                                links[j].click(); return 'text:'+links[j].innerText;
                            }
                        }
                    }""")
                    logger.info("Attempted JS login link click (fallback)")

                # Wait for login form to appear
                try:
                    await page.wait_for_selector("input[id='userID']", state="visible", timeout=10_000)
                    logger.info("Login form appeared (userID visible)")
                except Exception:
                    # Log all inputs visible for diagnosis
                    try:
                        inputs = await page.evaluate(
                            "() => Array.from(document.querySelectorAll('input,button,a'))"
                            ".map(e => e.tagName+'#'+(e.id||'')+'['+e.type+'] text='+(e.innerText||e.value||'').substring(0,30))"
                            ".join(' | ')"
                        )
                        logger.error("userID field not visible. Visible inputs: %s", inputs[:800])
                    except Exception:
                        logger.error("userID field not visible after login click")
                    return False

            # Step 2: Fill credentials
            user_id_el = page.locator("input[id='userID']").first
            await user_id_el.click(click_count=3)
            await user_id_el.fill(username)
            logger.info("Filled username: %s", username)

            password_el = page.locator("input[id='password']").first
            await password_el.click(click_count=3)
            await password_el.fill(password)
            logger.info("Filled password")

            # Step 3: Submit login
            submit_selectors = [
                "button[id='login_button']",
                "input[type='submit'][id*='login']",
                "button:has-text('Login')",
                "button:has-text('Submit')",
                "input[type='submit']",
            ]
            submitted = False
            for sel in submit_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3_000):
                        await el.click()
                        logger.info("Clicked login submit via: %s", sel)
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                logger.error("Login submit button not found")
                return False

            await asyncio.sleep(5)

            # Step 4: Check for login failure before proceeding
            try:
                body_text = await page.inner_text("body")
                if "Incorrect username or password" in body_text or "invalid" in body_text.lower() and "login" in body_text.lower():
                    # Dismiss any OK dialog
                    try:
                        ok_btn = page.locator("button:has-text('OK'), input[value='OK']").first
                        if await ok_btn.is_visible(timeout=2_000):
                            await ok_btn.click()
                    except Exception:
                        pass
                    logger.error("Login failed: portal rejected credentials (Incorrect username or password)")
                    return False
            except Exception as e:
                logger.warning("Could not check login result: %s", e)

            # Step 5: Reveal report elements that onload hid (only if login succeeded)
            await page.evaluate("""() => {
                var ids = ['appauth','gisdata','reportDiv','panelbody_report'];
                for (var i=0; i<ids.length; i++) {
                    var el = document.getElementById(ids[i]);
                    if (!el) continue;
                    if (ids[i] === 'appauth') { el.value = '1'; }
                    else { el.style.display = 'block'; }
                }
            }""")
            
            # Step 6: Handle "Already Logged" dialog and potentially re-submit
            try:
                dialog_handled = False
                for dialog_sel in [
                    "input[id='popupOKError']",
                    "button:has-text('OK')",
                    "input[value='OK']",
                ]:
                    dlg = page.locator(dialog_sel).first
                    if await dlg.is_visible(timeout=3_000):
                        await dlg.click()
                        logger.info("Clicked OK to dismiss 'Already Logged' dialog")
                        dialog_handled = True
                        await asyncio.sleep(2)
                        
                        # Re-submit login form once more after dismissing the block
                        logger.info("Re-submitting login form after dismissing 'Already Logged' block")
                        for sub_sel in submit_selectors:
                            sub_el = page.locator(sub_sel).first
                            if await sub_el.is_visible(timeout=2_000):
                                await sub_el.click()
                                break
                        await asyncio.sleep(5)
                        break
                if not dialog_handled:
                    logger.info("No 'Already Logged' dialog - session clear")
            except Exception as e:
                logger.warning("Error during 'Already Logged' dialog handling: %s", e)
            
            # Dump post-login page state for diagnostics
            try:
                post_login_url = page.url
                post_login_body = await page.evaluate("() => document.body.innerText.substring(0, 500)")
                logger.info("Post-login URL=%s body=%s", post_login_url, post_login_body)
                post_login_inputs = await page.evaluate(
                    "() => Array.from(document.querySelectorAll('button,a,li,input'))"
                    ".filter(el => el.offsetParent !== null)"
                    ".map(el => (el.id||'') + '|' + (el.innerText||el.value||'').substring(0,25))"
                )
                logger.info("Post-login visible elements: %s", post_login_inputs[:30])
            except Exception as e:
                logger.warning("Post-login diagnostic failed: %s", e)

            logger.info("Post-login: revealed report elements")
            return True

        except Exception as e:
            logger.error("DPRMarks login error: %s", e)
            return False

    async def _dprmarks_click_report(self, page: Page) -> bool:
        """Click the Report button (right side to search icon after login)."""
        try:
            logger.info("_dprmarks_click_report: URL=%s", page.url)
            for sel in [
                "button:has-text('Report')",
                "a:has-text('Report')",
                "li:has-text('Report')",
                "[id*='report']",
                "[class*='report']",
            ]:
                try:
                    el = page.locator(sel).first
                    visible = await el.is_visible()  # immediate check, no timeout
                    logger.debug("Report selector %s visible=%s", sel, visible)
                    if visible:
                        await el.click()
                        logger.info("Clicked Report button via: %s", sel)
                        await asyncio.sleep(2)
                        return True
                except Exception as e:
                    logger.debug("Report selector %s error: %s", sel, e)
                    continue

            # Fallback: try JS click on any element that contains the word "Report"
            logger.warning("No Report button found via selectors — trying JS click")
            try:
                js_result = await page.evaluate("""() => {
                    var all = document.querySelectorAll('button, a, li, span, div');
                    for (var el of all) {
                        var txt = (el.innerText || el.textContent || '').trim();
                        if (txt === 'Report' || txt === 'DP Report') {
                            el.click();
                            return 'clicked: ' + el.tagName + '#' + el.id + ' text=' + txt;
                        }
                    }
                    return 'not found';
                }""")
                logger.info("JS Report click result: %s", js_result)
                if "clicked" in str(js_result):
                    await asyncio.sleep(2)
                    return True
            except Exception as e:
                logger.warning("JS Report click failed: %s", e)

            return False
        except Exception as e:
            logger.error("DPRMarks report click error: %s", e)
            return False

    async def _dprmarks_fill_form(self, page: Page, ward: str, village: str, cts_no: str) -> bool:
        """Fill ward, village/division, CTS fields in the report form."""
        try:
            # Wait for the loading to finish first
            logger.info("Waiting for loading to finish...")
            try:
                await page.wait_for_selector("#loadingImg", state="hidden", timeout=60000)
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
                if await cts_dropdown.is_visible(timeout=5000):
                    await cts_dropdown.click()
                    await asyncio.sleep(1)
                    await cts_dropdown.fill(cts_no)
                    await asyncio.sleep(1)
                    
                    # Wait for dropdown options to appear
                    options = page.locator("li.ui-menu-item, li.ui-selectmenu-item, .ui-menu-item, [role='option']")
                    try:
                        await options.first.wait_for(timeout=3_000)
                        await page.keyboard.press("ArrowDown")
                        await asyncio.sleep(0.5)
                        await page.keyboard.press("Enter")
                        logger.info(f"Selected CTS: {cts_no}")
                    except Exception:
                        logger.warning(f"CTS {cts_no} not found in dropdown")
                        return False
                else:
                    logger.warning("SelectCTSR field not visible")
                    return False
            except Exception as e:
                logger.warning(f"Could not select CTS: {e}")
                return False

            return True

        except Exception as e:
            logger.error("DPRMarks form fill error: %s", e)
            return False

    async def _dprmarks_fill_form_fp(self, page: Page, ward: str, village: str, tps_scheme: str, fp_no: str) -> bool:
        """Fill ward, TPS scheme, FP number for the FP/2034 path."""
        try:
            await asyncio.sleep(2)

            # Diagnostic: log visible inputs to identify tab structure
            try:
                input_ids = await page.evaluate(
                    "() => Array.from(document.querySelectorAll('input,select,button,a,li'))"
                    ".filter(el => el.offsetParent !== null)"
                    ".map(el => (el.id || el.textContent.trim().substring(0,20)) + '|' + el.tagName)"
                )
                logger.info("FP form: visible elements: %s", input_ids[:40])
            except Exception:
                pass

            # Switch to FP tab — the form has CTS/CS and FP tabs
            fp_tab_switched = False
            
            # Debug: dump ALL text elements
            try:
                all_elements = await page.evaluate("""() => {
                    var items = document.querySelectorAll('li, a, span, div, button');
                    var results = [];
                    for (var el of items) {
                        if (el.offsetParent !== null) {
                            var txt = (el.innerText || el.textContent || '').trim().toUpperCase();
                            if (txt === 'FP' || txt === 'CTS/CS' || txt.includes('FP')) {
                                results.push(el.tagName + '|' + txt + '|' + (el.id || 'no-id'));
                            }
                        }
                    }
                    return results.join(' || ');
                }""")
                logger.info("FP tab debug elements: %s", all_elements)
            except Exception as e:
                logger.warning("Debug dump failed: %s", e)
            
            # Try clicking the LI element directly
            for tab_sel in [
                "li:has-text('FP')",
                "li.tab:has-text('FP')", 
                "[id*='FP']",
                "#fpTab",
                "a[href*='FP']",
            ]:
                try:
                    el = page.locator(tab_sel).first
                    if await el.is_visible(timeout=2_000):
                        await el.click()
                        await asyncio.sleep(1)
                        # Verify switched by checking if TPS field now appears
                        tps_check = page.locator("input[id='SelectTPSSchemeR']")
                        if await tps_check.is_visible(timeout=3_000):
                            logger.info("Switched to FP tab via: %s", tab_sel)
                            fp_tab_switched = True
                            await asyncio.sleep(1)
                            break
                        else:
                            logger.warning("Clicked %s but TPS field not visible, retrying...", tab_sel)
                except Exception as e:
                    logger.warning("FP tab selector %s failed: %s", tab_sel, e)
                    continue
            if not fp_tab_switched:
                logger.warning("FP tab not found - trying href selector")
                # Try #menuFP first (from user's HTML) then #menu2 fallback
                for menu_id in ["#menuFP", "#menu2"]:
                    try:
                        fp_link = page.locator(f"a[href='{menu_id}']").first
                        if await fp_link.is_visible(timeout=3000):
                            await fp_link.click()
                            logger.info("Clicked FP tab via href=%s", menu_id)
                            await asyncio.sleep(3)
                            
                            # Check if FP form fields are now visible
                            tps_field = page.locator("input[id='SelectTPSSchemeR']").first
                            if await tps_field.is_visible(timeout=3000):
                                fp_tab_switched = True
                                logger.info("FP tab switched, TPS field visible!")
                                break
                    except Exception as e:
                        logger.warning("href %s selector failed: %s", menu_id, e)
                        continue
                
                # JS fallback: find and click the FP tab
                js_result = await page.evaluate("""() => {
                    var items = document.querySelectorAll('li, a, span, div');
                    for (var el of items) {
                        var txt = (el.innerText || el.textContent || '').trim().toUpperCase();
                        if (txt === 'FP') {
                            el.click();
                            return 'clicked FP tab';
                        }
                    }
                    return 'not found';
                }""")
                if js_result == 'clicked FP tab':
                    fp_tab_switched = True
                    # Multiple strategies to ensure FP form loads
                    await asyncio.sleep(2)
                    logger.info("JS clicked FP tab, trying keyboard navigation...")
                    
                    # Try pressing Tab to get to FP tab, then Enter
                    for _ in range(5):
                        await page.keyboard.press("Tab")
                        await asyncio.sleep(0.5)
                    
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(3)
                    
                    # Also try direct URL with FP parameter
                    logger.info("Trying FP tab via direct click...")
                    try:
                        await page.evaluate("""() => {
                            var links = document.querySelectorAll('li, a, span');
                            for (var el of links) {
                                if ((el.innerText || '').trim().toUpperCase() === 'FP') {
                                    el.click();
                                    return 'clicked';
                                }
                            }
                            // Try clicking by tab order - FP is typically the second tab (index 1)
                            var tabs = document.querySelectorAll('[role=tab]');
                            if (tabs.length > 1) { tabs[1].click(); return 'tab[1]'; }
                            return 'not found';
                        }""")
                    except Exception as e:
                        logger.warning("Direct click failed: %s", e)
                    
                    await asyncio.sleep(3)
                    logger.info("FP tab click attempt complete, waiting for TPS field...")

            # Wait for FP form to fully load after tab switch
            await asyncio.sleep(2)
            
            try:
                inputs_after = await page.evaluate(
                    "() => Array.from(document.querySelectorAll('input'))"
                    ".filter(el => el.offsetParent !== null)"
                    ".map(el => el.id + '|' + el.type + '|' + el.name)"
                )
                logger.info("FP tab inputs after switch: %s", inputs_after)
            except Exception:
                pass

            # ====== PROPER DROPDOWN SELECTION ======
            async def select_dropdown_option(field_id: str, value: str, field_label: str):
                try:
                    field = page.locator(f"input[id='{field_id}']").first
                    if not await field.is_visible(timeout=5_000):
                        logger.warning(f"{field_label}: field not visible")
                        return False
                    
                    # JS logic to find exact item in store and select it
                    js_select = """([fieldId, val]) => {
                        try {
                            if (typeof dijit === 'undefined') return 'dijit_missing';
                            var d = dijit.byId(fieldId);
                            if (!d) return 'widget_missing';
                            
                            // Open dropdown to trigger data load if needed
                            try { d.loadDropDown(); d.openDropDown(); } catch(e) {}
                            
                            var items = (d.store && d.store.data) || (d.store && d.store._arrayOfAllItems) || [];
                            var matchedItem = null;
                            var searchAttr = d.searchAttr || 'name';
                            
                            for (var i=0; i<items.length; i++) {
                                var txtRaw = items[i][searchAttr];
                                var txt = Array.isArray(txtRaw) ? txtRaw[0] : txtRaw;
                                if (txt && (txt.toLowerCase().includes(val.toLowerCase()) || val.toLowerCase().includes(txt.toLowerCase()))) {
                                    matchedItem = items[i];
                                    break;
                                }
                            }
                            
                            if (matchedItem) {
                                d.set('item', matchedItem);
                                if (d.onChange) { d.onChange(d.get('value')); }
                                d.closeDropDown();
                                return 'selected:' + (Array.isArray(matchedItem[searchAttr]) ? matchedItem[searchAttr][0] : matchedItem[searchAttr]);
                            }
                            return 'not_found';
                        } catch(e) { return 'error:' + e; }
                    }"""
                    
                    for attempt in range(3):
                        result = await page.evaluate(js_select, [field_id, value])
                        logger.info(f"{field_label}: Selection attempt {attempt+1} result: {result}")
                        
                        if result.startswith('selected:'):
                            await asyncio.sleep(1)
                            # Verify displayed value
                            disp = await page.evaluate(f"() => dijit.byId('{field_id}').get('displayedValue')")
                            if disp and (value.lower() in disp.lower() or disp.lower() in value.lower()):
                                return True
                        
                        await asyncio.sleep(2) # Wait for store to load
                    return False
                except Exception as e:
                    logger.error(f"{field_label} error: {e}")
                    return False
                except Exception as e:
                    logger.warning(f"{field_label}: selection failed: {e}")
                    return False

            # Ward 
            await select_dropdown_option("SelectWardR2", ward, "FP path: Ward")
            await asyncio.sleep(3) # Wait for TPS to load based on Ward

            # Village/Division (Not needed for FP tab according to exact sequence)
            # The order must be Ward -> TPS Scheme -> FP

            # TPS Scheme
            tps_scheme_value = tps_scheme or village or "DADAR"  # fallback to ward name if no TPS
            await select_dropdown_option("SelectTPSR", tps_scheme_value, "FP path: TPS Scheme")
            await asyncio.sleep(3) # Wait for FP to load based on TPS

            # FP Number
            await select_dropdown_option("SelectFPR", fp_no, "FP path: FP Number")
            await asyncio.sleep(2)

            return True
        except Exception as e:
            logger.error("DPRMarks FP form fill error: %s", e)
            return False

    async def _dprmarks_click_next(self, page: Page, path: str = "cts", ward: str = None, village: str = None, tps_scheme: str = None, fp_no: str = None) -> bool:
        """
        path="cts":
          A. Click generateCTSreport
          B. Re-select CTS from secondary SelectCTSR to enable generateChallan
          C. Wait for generateChallan enabled (15s — returns False if not, for fallback detection)
          D. Click generateChallan (second Next)
        path="fp":
          A. Click generateFPreport
          B. Wait for generateChallan enabled (60s)
          C. Click generateChallan (second Next)
        """
        try:
            # A: Click first Next (path-specific button)
            clicked = False
            if path == "cts":
                first_next_sels = ["input[id='generateCTSreport']", "button[id='generateCTSreport']"]
            else:
                first_next_sels = ["input[id='generateFPreport']", "button[id='generateFPreport']"]

            for sel in first_next_sels:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3000):
                        await el.click()
                        logger.info("Clicked first Next button (%s)", sel)
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                logger.warning("First Next button not found")
                return False

            await asyncio.sleep(5)

            # After clicking first Next, there may be a popup dialog (e.g., "Select Ward.").
            # Handle it BEFORE waiting for generateChallan.
            try:
                popup_ok = page.locator("input[id='popupOKError']").first
                if await popup_ok.is_visible(timeout=5_000):
                    await popup_ok.click()
                    logger.info("Closed popup after first Next")
                    await asyncio.sleep(2)
            except Exception:
                pass

            # Diagnostic: log page content after generateCTSreport to identify
            # what secondary CTS selector the portal renders
            try:
                page_body = await page.evaluate(
                    "() => document.body.innerText.substring(0, 1500)"
                )
                logger.info("Page after generateCTSreport click: %s", page_body)
                # Also log all input IDs visible at this point
                input_ids = await page.evaluate(
                    "() => Array.from(document.querySelectorAll('input,select,button'))"
                    ".filter(el => el.offsetParent !== null)"
                    ".map(el => el.id + '|' + el.type + '|' + el.disabled)"
                )
                logger.info("Visible inputs after generateCTSreport: %s", input_ids[:50])
            except Exception as e:
                logger.warning("Could not read page after generateCTSreport: %s", e)

            # Handle popup that may appear after form submissions (e.g., "Select Ward." or "Already Logged" or "Add parcels...")
            try:
                page_text = await page.evaluate("() => document.body.innerText")
                logger.info("Popup check: page text = %s", page_text[:300])
                
                # Check for "Add parcels" popup - this has the generateChallan button inside it
                if "Add parcels" in page_text or "Add More" in page_text:
                    logger.info("Detected Add parcels popup - clicking generateChallan (Next in popup)...")
                    popup_gc = page.locator("input[id='generateChallan']").first
                    if await popup_gc.is_visible(timeout=3000):
                        await popup_gc.click()
                        logger.info("Clicked generateChallan in popup!")
                        await asyncio.sleep(3)
                        
                        # Check if we're now on payment page
                        new_page = await page.evaluate("() => document.body.innerText")
                        if "Payment" in new_page or "Bank" in new_page or "Indian" in new_page:
                            logger.info("Reached payment page!")
                            return True
                    else:
                        logger.warning("generateChallan not found in Add parcels popup")
                
                # Handle other popups like "Select Ward"
                if "Select Ward" in page_text or "SelectWard" in page_text:
                    # Try multiple selectors for the OK button
                    for sel in ["input[id='popupOKError']", "button[id='popupOKError']", "input[value='OK']", "button:has-text('OK')"]:
                        try:
                            btn = page.locator(sel).first
                            if await btn.is_visible(timeout=1_000):
                                await btn.click()
                                logger.info("Closed popup with selector: %s", sel)
                                break
                        except Exception:
                            continue
                    await asyncio.sleep(2)
            except Exception as e:
                logger.warning("Popup handler error: %s", e)

            # Check if on map page now - close any login overlay first
            try:
                page_text = await page.evaluate("() => document.body.innerText")
                logger.info("After generateFPreport: %s", page_text[:300])
                if "CTS/CS/FP Nos Selected" in page_text or "Map" in page_text:
                    logger.info("On map page - trying to close login overlay")
                    
                    # Close any overlay/popup that might block clicks
                    # Try close button with various selectors
                    for close_sel in ["a[id*='popupBoxCloseError']", "span[class*='close']", "button:has-text('X')]", "a:has-text('X')"]:
                        try:
                            close_btn = page.locator(close_sel).first
                            if await close_btn.is_visible(timeout=1000):
                                await close_btn.click()
                                logger.info("Closed overlay with: %s", close_sel)
                                await asyncio.sleep(1)
                                break
                        except Exception:
                            pass
                    
                    # Click in corner to dismiss any floating panel
                    try:
                        await page.mouse.click(10, 10)
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
                    
                    logger.info("On map page - ready for generateChallan")
            except Exception:
                pass
            # ====== END ADD ======

            # Click ALL "Next" buttons on the page until we reach payment
            # There are multiple Next buttons in the flow:
            # 1. generateChallan (2nd Next) 
            # 2. Any other "Next" button
            
            await asyncio.sleep(2)
            
            # Try all possible Next button selectors
            next_selectors = [
                "input[id='generateChallan']",
                "button[id='generateChallan']",
                "input[value='Next']",
                "button:has-text('Next')", 
                "input[value='next']",
                "button:has-text('next')",
                "[id*='next']",
            ]
            
            logger.info("Looking for Next buttons on map page...")
            
            # After generateFPreport, check if generateChallan is now enabled
            # If generateFPreport was clicked and page changed, generateChallan should work
            try:
                gc = page.locator("input[id='generateChallan']").first
                if await gc.is_visible(timeout=3000):
                    gc_disabled = await gc.is_disabled()
                    if not gc_disabled:
                        logger.info("generateChallan is enabled - clicking it!")
                        await gc.click()
                        logger.info("Clicked generateChallan (map → payment)")
                        await asyncio.sleep(5)
                        
                        # Check for payment page
                        page_text = await page.evaluate("() => document.body.innerText")
                        if "Payment" in page_text or "Bank" in page_text or "Indian" in page_text:
                            logger.info("Reached payment page!")
                            return True
                    else:
                        logger.info("generateChallan still disabled - need ADD to add FP to selection")
                        
                        # Try clicking ADD MORE to add the selected FP to the list
                        # First close login overlay and hide it via JS
                        try:
                            await page.evaluate("""() => {
                                var loginDiv = document.getElementById('user_login_div');
                                if (loginDiv) loginDiv.style.display = 'none';
                                var errPopup = document.getElementById('popupBoxCloseError');
                                if (errPopup) errPopup.click();
                            }""")
                            overlay_close = page.locator("a[id='popupBoxCloseError']").first
                            if await overlay_close.is_visible(timeout=1000):
                                await overlay_close.click()
                                logger.info("Closed login overlay before addSelection")
                                await asyncio.sleep(1)
                        except Exception:
                            pass
                        
                        # Now try addSelection
                        try:
                            # Try regular click first
                            add_btn = page.locator("input[id='addSelection']").first
                            if await add_btn.is_visible(timeout=3000):
                                await add_btn.click()
                                logger.info("Clicked addSelection to add FP to selection list")
                                await asyncio.sleep(3)
                        except Exception as e:
                            logger.warning("addSelection regular click failed: %s, trying JS", e)
                            # Try JS click as fallback
                            try:
                                result = await page.evaluate("""() => {
                                    var btn = document.getElementById('addSelection');
                                    if (btn) { btn.click(); return 'clicked addSelection'; }
                                    return 'not found';
                                }""")
                                logger.info("JS click result: %s", result)
                                await asyncio.sleep(3)
                            except Exception as js_err:
                                logger.warning("JS click also failed: %s", js_err)
                        
                        # Wait and check if generateChallan is now enabled
                        await asyncio.sleep(3)
                        try:
                            gc2 = page.locator("input[id='generateChallan']").first
                            if await gc2.is_visible(timeout=3000):
                                gc2_disabled = await gc2.is_disabled()
                                if not gc2_disabled:
                                    gc2.click()
                                    logger.info("Clicked generateChallan after addSelection")
                                    await asyncio.sleep(5)
                                    return True
                                else:
                                    logger.info("generateChallan still disabled after add")
                        except Exception as e:
                            logger.warning("generateChallan check after add failed: %s", e)
            except Exception as e:
                logger.warning("generateChallan check failed: %s", e)
            
            # Log all form elements on page to understand structure
            try:
                forms = await page.evaluate("""() => {
                    var results = [];
                    document.querySelectorAll('form').forEach(f => {
                        results.push('form id=' + f.id + ' action=' + f.action);
                    });
                    document.querySelectorAll('input[type=checkbox]').forEach(cb => {
                        results.push('checkbox id=' + cb.id + ' name=' + cb.name + ' checked=' + cb.checked);
                    });
                    return results.join(' || ');
                }""")
                logger.info("Forms/checkboxes on page: %s", forms)
            except Exception as e:
                logger.warning("Form check failed: %s", e)
            
            # Map page: need to find what triggers Create Challan - try all buttons/checkboxes
            try:
                # Also hide any blocking overlays
                await page.evaluate("""() => {
                    var loginDiv = document.getElementById('user_login_div');
                    if (loginDiv) loginDiv.style.display = 'none';
                    var errPopup = document.getElementById('popupBoxCloseError');
                    if (errPopup) errPopup.click();
                }""")
                await asyncio.sleep(1)
                
                map_interact = await page.evaluate("""() => {
                    var results = [];
                    // Check all checkboxes using dijit if possible
                    document.querySelectorAll('input').forEach(inp => {
                        var type = inp.type || 'text';
                        if (type === 'checkbox') {
                            if (!inp.checked) {
                                try {
                                    var d = typeof dijit !== 'undefined' ? dijit.byId(inp.id) : null;
                                    if (d) { d.set('checked', true); } else { inp.click(); }
                                } catch(e) { inp.click(); }
                                results.push('checked: ' + inp.id);
                            }
                        }
                    });
                    
                    // After checking checkboxes, we might need to click addSelection
                    try {
                        var addBtn = typeof dijit !== 'undefined' ? dijit.byId('addSelection') : null;
                        if (addBtn) { addBtn.click(); results.push('dijit clicked addSelection'); }
                        else {
                            var el = document.getElementById('addSelection');
                            if (el) { el.click(); results.push('dom clicked addSelection'); }
                        }
                    } catch(e) {}
                    
                    return results.join(' || ');
                }""")
                logger.info("Map page interaction result: %s", map_interact)
                
                await asyncio.sleep(4)
                
                # Try clicking generateChallan normally now that checkboxes are checked
                try:
                    gc3 = page.locator("input[id='generateChallan']").first
                    if await gc3.is_visible(timeout=2000):
                        if not await gc3.is_disabled():
                            await gc3.click()
                            logger.info("Clicked generateChallan after checking checkboxes!")
                            await asyncio.sleep(5)
                            # Check page for challan summary
                            page_text = await page.evaluate("() => document.body.innerText")
                            if "Consumer Details" in page_text or "Create Challan" in page_text:
                                logger.info("Reached challan summary page!")
                                return True
                except Exception as e:
                    logger.warning("Normal generateChallan click failed after checkboxes: %s", e)
                
                # Try submitting form directly
                form_submit = await page.evaluate("""() => {
                    var forms = document.querySelectorAll('form');
                    for (var f of forms) {
                        // Try dijit form submit
                        if (f.id && f.id.length > 0) {
                            try { 
                                var d = dijit.byId(f.id);
                                if (d && d.submit) { d.submit(); return 'dijit.submit ' + f.id; }
                            } catch(e) {}
                        }
                    }
                    // Try generateChallan via dijit
                    try {
                        var gc = dijit.byId('generateChallan');
                        if (gc) { gc.click(); return 'dijit.click generateChallan'; }
                    } catch(e) {}
                    // Try triggering onClick directly
                    try {
                        var btn = document.getElementById('generateChallan');
                        if (btn && !btn.disabled) { btn.click(); return 'click generateChallan'; }
                        if (btn && btn.onclick) { btn.onclick(); return 'onclick generateChallan'; }
                    } catch(e) {}
                    return 'no form submit';
                }""")
                logger.info("Form submit result: %s", form_submit)
                await asyncio.sleep(5)
                
                # Check page for challan summary
                page_text = await page.evaluate("() => document.body.innerText")
                if "Consumer Details" in page_text or "Create Challan" in page_text:
                    logger.info("Reached challan summary page!")
                    return True
                
                # Try pressing Enter key to submit
                await page.keyboard.press("Enter")
                await asyncio.sleep(3)
                page_text = await page.evaluate("() => document.body.innerText")
                logger.info("After Enter key: %s", page_text[:300])
                if "Consumer Details" in page_text or "Create Challan" in page_text:
                    logger.info("Reached challan summary page!")
                    return True
            except Exception as e:
                logger.warning("Map page interaction failed: %s", e)
            try:
                # Try multiple approaches to click Next
                for attempt in range(3):
                    clicked = await page.evaluate(f"""(attempt) => {{
                        // Try clicking generateChallan button
                        var gc = document.getElementById('generateChallan');
                        if (gc && gc.offsetParent !== null) {{
                            gc.click();
                            return 'clicked generateChallan';
                        }}
                        
                        // Try any button with NEXT value
                        var inputs = document.querySelectorAll('input[value*="Next"], input[value*="next"]');
                        for (var inp of inputs) {{
                            if (inp.offsetParent !== null) {{
                                inp.click();
                                return 'clicked input Next';
                            }}
                        }}
                        
                        // Try buttons
                        var btns = document.querySelectorAll('button');
                        for (var btn of btns) {{
                            if (btn.offsetParent !== null) {{
                                var txt = (btn.value || btn.innerText || '').toUpperCase();
                                if (txt.includes('NEXT')) {{
                                    btn.click();
                                    return 'clicked button: ' + txt;
                                }}
                            }}
                        }}
                        
                        return 'no button found attempt ' + attempt;
                    }}""", attempt)
                    logger.info("JS click attempt %d: %s", attempt + 1, clicked)
                    await asyncio.sleep(3)
                    
                    # Check page
                    new_page = await page.evaluate("() => document.body.innerText")
                    logger.info("After click page: %s", new_page[:200])
                    
                    if "Consumer Details" in new_page or "Create Challan" in new_page:
                        logger.info("Reached challan summary page!")
                        return True
            except Exception as e:
                logger.warning("JS click failed: %s", e)

            # C: Wait for generateChallan to become NOT disabled
            # CTS path: 15s timeout — if it doesn't enable, the CTS is not in dropdown;
            # caller will fall back to FP path. FP path: 60s.
            challan_wait_ms = 15_000 if path == "cts" else 60_000
            logger.info("Waiting for generateChallan to be enabled (timeout=%ds, path=%s)...", challan_wait_ms // 1000, path)
            # Was used for debugging, left here originally; no longer necessary
            try:
                await page.wait_for_function(
                    "() => {"
                    "  var el = document.querySelector(\"input[id='generateChallan']\") "
                    "         || document.querySelector(\"button[id='generateChallan']\");"
                    "  return el && !el.disabled;"
                    "}",
                    timeout=challan_wait_ms,
                )
                logger.info("generateChallan is now enabled")
            except Exception as e:
                logger.warning("generateChallan enabled-wait timed out (%s)", e)
                if path == "cts":
                    logger.warning("CTS not in dropdown (generateChallan never enabled) — caller should try FP path")
                    return False

            # D: Click generateChallan (second Next) — challan summary loads in same tab
            for sel in ["input[id='generateChallan']", "button[id='generateChallan']"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=5_000):
                        await el.click()
                        logger.info("Clicked generateChallan (second Next)")
                        await asyncio.sleep(5)
                        logger.info("After generateChallan: URL=%s", page.url)
                        return True
                except Exception:
                    continue

            logger.warning("generateChallan button not found for click")
            return False

        except Exception as e:
            logger.error("DPRMarks Next click error: %s", e)
            return False

    async def _dprmarks_fill_consumer_details(self, page: Page) -> bool:
        """
        Fill the 'Enter Consumer Details' form on the challan summary page.
        MCGM portal requires applicant name + mobile before generating challan.
        """
        # Hide loading spinner that might block clicks
        try:
            await page.evaluate("""() => {
                var load = document.getElementById('loadingImg');
                if (load) load.style.display = 'none';
            }""")
        except Exception:
            pass

        from ..core import settings

        consumer_name = getattr(settings, "DPRMARKS_CONSUMER_NAME", "") or "Dhiraj Kunj CHS"
        consumer_mobile = getattr(settings, "DPRMARKS_CONSUMER_MOBILE", "") or "9999999999"
        consumer_email = getattr(settings, "DPRMARKS_CONSUMER_EMAIL", "") or "info@dhara.ai"
        consumer_address = "Mumbai"

        filled = False
        name_selectors = [
            "input[id='consumerName']",
            "input[id='firstname']",
            "input[id='firstName']",
            "input[name='firstName']",
            "input[id='inputConsumerName']",
            "input[name='consumerName']",
            "input[placeholder*='Name']",
            "input[placeholder*='Consumer']",
            "input[id*='consumer'][id*='ame']",
        ]
        for sel in name_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2_000):
                    await el.click(click_count=3)
                    await el.fill(consumer_name)
                    logger.info("Filled consumer name via: %s", sel)
                    filled = True
                    break
            except Exception:
                continue

        # Also try to fill surname and lastname if it exists
        try:
            surname_el = page.locator("input[id='surname']").first
            if await surname_el.is_visible(timeout=1000):
                await surname_el.fill("CHS")
                logger.info("Filled surname")
        except Exception:
            pass
            
        try:
            lastname_el = page.locator("input[id='lastname']").first
            if await lastname_el.is_visible(timeout=1000):
                await lastname_el.fill("CHS")
                logger.info("Filled lastname")
        except Exception:
            pass

        mobile_selectors = [
            "input[id='mobileNo']",
            "input[id='mobile']",
            "input[name='mobile']",
            "input[id='inputMobileNo']",
            "input[name='mobileNo']",
            "input[placeholder*='Mobile']",
            "input[placeholder*='Phone']",
            "input[id*='mobile']",
        ]
        for sel in mobile_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2_000):
                    await el.click(click_count=3)
                    await el.fill(consumer_mobile)
                    logger.info("Filled consumer mobile via: %s", sel)
                    filled = True
                    break
            except Exception:
                continue

        if consumer_email:
            email_selectors = [
                "input[id='emailaddress']",
                "input[id='emailId']",
                "input[type='email']",
                "input[placeholder*='Email']",
            ]
            for sel in email_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2_000):
                        await el.click(click_count=3)
                        await el.fill(consumer_email)
                        logger.info("Filled consumer email via: %s", sel)
                        break
                except Exception:
                    continue
                    
        # Fill address
        try:
            addr_el = page.locator("input[id='addressUser'], textarea[id='addressUser']").first
            if await addr_el.is_visible(timeout=1000):
                await addr_el.fill(consumer_address)
                logger.info("Filled consumer address")
        except Exception:
            pass

        if not filled:
            # Dump all inputs to help diagnose form structure
            try:
                all_inputs = await page.evaluate(
                    "() => Array.from(document.querySelectorAll('input,select,textarea'))"
                    ".filter(el => el.offsetParent !== null)"
                    ".map(el => el.id + '|' + el.name + '|' + el.placeholder + '|' + el.type)"
                )
                logger.warning("Consumer details form fields not found. Visible inputs: %s", all_inputs[:30])
            except Exception:
                pass

        return filled

    async def _dprmarks_click_challan_capture_popup(self, page: Page):
        """
        After generateChallan loads the challan summary ('Enter Consumer Details'),
        fill the form and click 'Create Challan', which may:
        - Open a bank selection popup (new window)
        - Navigate same-tab to a payment/bank selection page
        Returns the Page with bank selection (popup or same page), or None on failure.

        NOTE: The portal SPA keeps URL 'dp2034/login#' even on authenticated pages.
        Do NOT treat this URL as a session expiry indicator.
        """
        # Wait for the challan summary page to fully load
        await asyncio.sleep(3)

        # Log URL + full page content to understand state
        logger.info("Challan summary: URL=%s", page.url)
        try:
            body_preview = await page.evaluate("() => document.body.innerText.substring(0, 800)")
            logger.info("Challan page content: %s", body_preview)
        except Exception:
            pass
        try:
            cookies = await page.context.cookies()
            logger.info("Active cookies: %s", [c["name"] for c in cookies])
        except Exception:
            pass

        # Dump all form fields to identify IDs before filling
        try:
            all_form_fields = await page.evaluate(
                "() => Array.from(document.querySelectorAll('input,select,textarea'))"
                ".map(el => el.id + '|' + el.name + '|' + el.placeholder + '|' + el.type + '|vis=' + (el.offsetParent !== null))"
            )
            logger.info("Consumer details form fields: %s", all_form_fields)
        except Exception:
            pass

        # Also dump innerHTML of the consumer details section
        try:
            section_html = await page.evaluate(
                "() => { var el = document.querySelector('#consumerDetailsDiv, #consumerForm, [id*=consumer], [id*=Consumer]'); "
                "return el ? el.innerHTML.substring(0, 2000) : 'not found'; }"
            )
            logger.info("Consumer details section HTML: %s", section_html[:500])
        except Exception:
            pass

        # Fill consumer details if the form is present
        await self._dprmarks_fill_consumer_details(page)
        await asyncio.sleep(1)

        # Find the "Create Challan" button
        create_selectors = [
            "button:has-text('Create Challan')",
            "input[value='Create Challan']",
            "a:has-text('Create Challan')",
            "button:has-text('Proceed to Pay')",
            "input[value='Proceed to Pay']",
            "input[type='submit'][value*='Challan']",
        ]
        create_el = None
        for sel in create_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=5_000):
                    create_el = el
                    logger.info("Found 'Create Challan' button via: %s", sel)
                    break
            except Exception:
                continue

        if create_el is None:
            try:
                body = await page.evaluate("() => document.body.innerText.substring(0, 1000)")
                logger.error("'Create Challan' not found. Page text: %s", body)
            except Exception:
                logger.error("'Create Challan' not found and could not read page text")
            return None

        # Log the button's attributes for diagnosis
        try:
            btn_info = await page.evaluate(
                "() => { var b = document.querySelector(\"button:contains('Create Challan'), button\"); "
                "if (!b) return 'btn not found'; "
                "return b.outerHTML; }"
            )
            logger.info("Create Challan button HTML: %s", btn_info)
        except Exception:
            pass

        # Attempt popup capture first
        logger.info("Clicking 'Create Challan' — capturing bank selection popup...")
        try:
            async with page.expect_popup(timeout=15_000) as popup_info:
                # Use evaluate click first, it's more reliable if there are pointer-events: none issues
                await create_el.evaluate("b => b.click()")
            bank_page = await popup_info.value()
            await bank_page.wait_for_load_state("domcontentloaded", timeout=20_000)
            title = await bank_page.title()
            logger.info("Bank selection popup: url=%s  title=%s", bank_page.url, title)
            visible = await bank_page.evaluate(
                "() => document.body ? document.body.innerText.substring(0, 500) : ''"
            )
            logger.info("Bank popup body: %s", visible)
            return bank_page
        except Exception as e:
            logger.warning("No popup from 'Create Challan': %s", e)

        # No popup — check if same-tab navigation occurred
        await asyncio.sleep(3)
        current_url = page.url
        try:
            after_body = await page.evaluate("() => document.body.innerText.substring(0, 800)")
            logger.info("After Create Challan click — URL=%s  body=%s", current_url, after_body)
        except Exception:
            logger.info("After Create Challan click — URL=%s", current_url)

        # Check for validation error text on the page
        try:
            err_text = await page.evaluate(
                "() => { var errs = document.querySelectorAll('.error, .alert, [class*=error], [class*=Error], [id*=error], [id*=Error]'); "
                "return Array.from(errs).map(e => e.innerText).join(' | '); }"
            )
            if err_text.strip():
                logger.warning("Validation errors on page: %s", err_text[:300])
        except Exception:
            pass

        # Try JS-direct click as fallback (bypasses Playwright event interception)
        try:
            popup_found = await page.evaluate(
                "() => new Promise((resolve) => { "
                "  var orig = window.open; "
                "  window.open = function(url, name, features) { "
                "    window._capturedPopupUrl = url; "
                "    return orig.call(window, url, name, features); "
                "  }; "
                "  var btns = document.querySelectorAll('button, input[type=submit]'); "
                "  for (var b of btns) { "
                "    if (b.innerText.includes('Create Challan') || b.value === 'Create Challan') { "
                "      b.click(); break; "
                "    } "
                "  } "
                "  setTimeout(() => resolve(window._capturedPopupUrl || null), 2000); "
                "})"
            )
            if popup_found:
                logger.info("JS click captured popup URL: %s", popup_found)
        except Exception as e:
            logger.debug("JS click fallback: %s", e)

        # If URL changed to something outside dpremarks, it's a payment redirect
        if "dpremarks.mcgm.gov.in" not in current_url:
            logger.info("Same-tab navigation to payment page: %s", current_url)
            return page

        # Still on dpremarks — check if page content changed (bank selection loaded in-place)
        try:
            bank_keywords = ["Indian Bank", "Maharashtra Bank", "Citi Bank", "Select Bank",
                             "CCAvenue", "Payment", "Bank"]
            body_text = await page.evaluate("() => document.body.innerText")
            if any(kw.lower() in body_text.lower() for kw in bank_keywords):
                logger.info("Bank selection appears to be loaded in same page")
                return page
        except Exception:
            pass

        logger.error("'Create Challan' clicked but no popup or navigation. URL=%s", current_url)
        return None


    def _load_test_pdf(self) -> bytes:
        """Load the pre-existing test PDF for SKIP_PAYMENT mode."""
        from ..core import settings
        path = settings.TEST_DP_PDF_PATH
        if not path:
            here = Path(__file__).resolve()
            for parent in here.parents:
                candidate = parent / "test_docs" / "DP Remark 2034 FP 18.pdf"
                if candidate.exists():
                    path = str(candidate)
                    break
        if not path or not Path(path).exists():
            raise FileNotFoundError(
                "Test DP PDF not found. Set TEST_DP_PDF_PATH or place PDF at "
                "<repo_root>/test_docs/DP Remark 2034 FP 18.pdf"
            )
        return Path(path).read_bytes()

    async def _download_report_pdf(self, page: Page) -> bytes | None:
        """Download the DP Remark PDF after payment confirmation."""
        try:
            for sel in [
                "a:has-text('Download')",
                "a:has-text('Print')",
                "button:has-text('Download Report')",
                "a[href*='.pdf']",
                "a[href*='download']",
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=5_000):
                        async with page.expect_download(timeout=30_000) as dl_info:
                            await el.click()
                        download = await dl_info.value
                        pdf_path = await download.path()
                        return Path(pdf_path).read_bytes()
                except Exception:
                    continue

            # Fallback: check if page IS a PDF
            try:
                content_type = await page.evaluate(
                    "document.contentType || document.mimeType || ''"
                )
                if "pdf" in content_type.lower():
                    return await page.pdf()
            except Exception:
                pass

            logger.warning("No download link found after payment")
            return None

        except Exception as e:
            logger.error("PDF download error: %s", e)
            return None

    async def _read_dprmarks_page_text(self, page: Page) -> str | None:
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


def _parse_popup_text(text: str) -> dict | None:
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

    lines = [line.strip() for line in text.splitlines() if line.strip()]
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
