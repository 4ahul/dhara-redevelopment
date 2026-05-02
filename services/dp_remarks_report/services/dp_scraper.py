"""
DP Report Service — Browser Scraper (Playwright)
Automates MCGM's online DP map portals to fetch Development Plan remarks.
"""

import asyncio
import base64
import datetime
import logging
import re
from pathlib import Path

from playwright.async_api import Page, Response, async_playwright

logger = logging.getLogger(__name__)

# DP 2034 public map
DP_MAP_URL = "https://mcgmapp.mcgm.gov.in/DP2034/"

# DPRMarks portal (requires login)
DPREMARKS_URL = "https://dpremarks.mcgm.gov.in/dp2034/"

APP_LOAD_TIMEOUT = 60_000  # ms


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
        playwright = None
        browser = None
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(viewport={"width": 1920, "height": 1080})
            page = await context.new_page()
            
            # Navigate and Login
            await page.goto(DPREMARKS_URL, timeout=APP_LOAD_TIMEOUT)
            await asyncio.sleep(5)
            
            if not await self._dprmarks_login(page):
                return {"error": "Login failed"}
                
            if not await self._dprmarks_click_report(page):
                return {"error": "Report button failed"}

            # Fill Form
            fp_no_for_form = fp_no or cts_no
            if not await self._dprmarks_fill_form_fp(page, ward, village, tps_scheme, fp_no_for_form):
                return {"error": "Form fill failed"}
            
            # Next buttons
            if not await self._dprmarks_click_next(page, path="fp", fp_no=fp_no_for_form):
                return {"error": "Next navigation failed"}

            # Payment Popup
            bank_page = await self._dprmarks_click_challan_capture_popup(page)
            if not bank_page:
                return {"error": "Bank popup failed"}
            
            return {"attributes": {"status": "reached_payment"}, "url": bank_page.url}

        except Exception as e:
            logger.error("Scraper error: %s", e)
            return {"error": str(e)}
        finally:
            if browser: await browser.close()
            if playwright: await playwright.stop()

    async def _dprmarks_login(self, page: Page) -> bool:
        from ..core import settings
        try:
            await page.evaluate("() => { var el = document.getElementById('user_login'); if (el) el.click(); }")
            await asyncio.sleep(2)
            await page.locator("#userID").fill(settings.DPRMARKS_USERNAME)
            await page.locator("#password").fill(settings.DPRMARKS_PASSWORD)
            await page.locator("#login_button").click()
            await asyncio.sleep(5)
            # Dismiss any 'Already Logged'
            try:
                ok = page.locator("input[id='popupOKError']").first
                if await ok.is_visible(timeout=2000):
                    await ok.click()
                    await asyncio.sleep(1)
                    await page.locator("#login_button").click()
                    await asyncio.sleep(5)
            except Exception: pass
            return True
        except Exception: return False

    async def _dprmarks_click_report(self, page: Page) -> bool:
        try:
            await page.locator("button:has-text('Report')").first.click()
            await asyncio.sleep(3)
            return True
        except Exception: return False

    async def _dprmarks_fill_form_fp(self, page: Page, ward: str, village: str, tps_scheme: str, fp_no: str) -> bool:
        try:
            # Helpers
            async def select_dropdown_option(field_id: str, value: str, label: str):
                js_select = """([fieldId, val]) => {
                    return new Promise((resolve) => {
                        var d = dijit.byId(fieldId);
                        if (!d) { resolve('missing'); return; }
                        try { d.loadDropDown(); d.openDropDown(); } catch(e) {}
                        var check = () => {
                            var items = (d.store && d.store.data) || (d.store && d.store._arrayOfAllItems) || [];
                            var normalize = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
                            var normVal = normalize(val);
                            var best = null, max = 0;
                            for (var i=0; i<items.length; i++) {
                                var txt = items[i][d.searchAttr || 'name'];
                                if (Array.isArray(txt)) txt = txt[0];
                                var n = normalize(txt);
                                var score = (n === normVal) ? 100 : (n.includes(normVal) ? 50 : 0);
                                if (score > max) { max = score; best = items[i]; }
                            }
                            if (best) {
                                d.set('item', best);
                                if (d.onChange) d.onChange(d.get('value'));
                                resolve('selected'); return true;
                            }
                            return false;
                        };
                        var start = Date.now();
                        var iv = setInterval(() => {
                            if (check() || Date.now()-start > 8000) {
                                clearInterval(iv);
                                if (Date.now()-start > 8000) resolve('not_found');
                            }
                        }, 500);
                    });
                }"""
                res = await page.evaluate(js_select, [field_id, value])
                logger.info(f"{label}: {res}")
                return res == 'selected'

            async def select_via_popup(field_id: str, value: str, label: str):
                try:
                    # Click arrow
                    arrow = page.locator(f"input[id='{field_id}'] ~ .dijitArrowButtonInner, .dijitComboBox[id*='{field_id}'] .dijitArrowButtonInner").first
                    if await arrow.is_visible(timeout=2000): await arrow.click()
                    else: await page.locator(f"input[id='{field_id}']").first.click()
                    await asyncio.sleep(1)
                    # Click item
                    item = page.locator(f"div[id*='{field_id}_popup'] div:has-text('{value}'), .dijitMenuItem:has-text('{value}')").first
                    if await item.is_visible(timeout=3000):
                        await item.click()
                        logger.info(f"{label} via popup click")
                        return True
                except Exception: pass
                return await select_dropdown_option(field_id, value, label)

            # 1. Prime Ward in CTS tab
            await select_via_popup("SelectWardR", ward, "Ward Prime")
            await asyncio.sleep(2)
            
            # 2. Switch to FP tab
            await page.evaluate("() => { var links = document.querySelectorAll('a'); for (var l of links) if (l.innerText.trim() === 'FP') l.click(); }")
            await asyncio.sleep(3)
            
            # 3. Fill FP form
            await select_via_popup("SelectWardR2", ward, "Ward FP")
            await asyncio.sleep(10)
            
            tps_val = tps_scheme or village or "DADAR"
            await select_via_popup("SelectTPSR", tps_val, "TPS")
            await asyncio.sleep(5)
            
            await select_via_popup("SelectFPR", fp_no, "FP")
            await asyncio.sleep(2)
            
            return True
        except Exception as e:
            logger.error("FP fill error: %s", e)
            return False

    async def _dprmarks_click_next(self, page: Page, path: str = "cts", fp_no: str = None) -> bool:
        try:
            btn_id = "generateFPreport" if path == "fp" else "generateCTSreport"
            await page.locator(f"#{btn_id}").click()
            await asyncio.sleep(5)
            
            # Map -> Consumer Details loop
            for i in range(5):
                # Remove overlays
                await page.evaluate("""() => {
                    ['loadingImg', 'loadingImg2', 'user_login_div', 'popupOKError', 'popupBoxCloseError'].forEach(id => {
                        var e = document.getElementById(id); if (e) e.remove();
                    });
                    document.querySelectorAll('.LoadingDiv, .loader, .spinner, .dijitDialog').forEach(e => e.remove());
                }""")
                
                if await page.locator("#firstname").is_visible(timeout=1000):
                    logger.info("Reached consumer details!")
                    return True
                
                # Check for "Add parcels" popup
                text = await page.evaluate("() => document.body.innerText")
                if "Add parcels" in text or "Add More" in text:
                    await page.evaluate("() => { var b = document.getElementById('generateChallan'); if (b) b.click(); }")
                    await asyncio.sleep(3)
                    continue

                # Normal click
                res = await page.evaluate("""() => {
                    var b = document.getElementById('generateChallan');
                    if (b && !b.disabled) { b.click(); return 'clicked'; }
                    var a = document.getElementById('addSelection');
                    if (a) { a.click(); return 'added'; }
                    return 'waiting';
                }""")
                logger.info(f"Map transition attempt {i}: {res}")
                await asyncio.sleep(5)
            return False
        except Exception: return False

    async def _dprmarks_click_challan_capture_popup(self, page: Page):
        await self._dprmarks_fill_consumer_details(page)
        try:
            async with page.expect_popup(timeout=30000) as popup_info:
                # Use trusted click
                await page.locator("button:has-text('Create Challan'), input[value='Create Challan']").first.click()
            return await popup_info.value
        except Exception:
            # Try evaluate fallback
            try:
                async with page.expect_popup(timeout=10000) as popup_info:
                    await page.evaluate("() => { var b = document.getElementById('btnCreateChallan') || document.querySelector('button'); b.click(); }")
                return await popup_info.value
            except Exception: return None

    async def _dprmarks_fill_consumer_details(self, page: Page) -> bool:
        try:
            now = datetime.datetime.now().strftime("%H%M%S")
            name = "Dhara " + now
            mobile = "9" + datetime.datetime.now().strftime("%y%m%d%H%M")[:9]
            await page.locator("#firstname").fill(name)
            await page.locator("#surname").fill("AI")
            await page.locator("#mobile").fill(mobile)
            await page.locator("#emailaddress").fill("info@dhara.ai")
            await page.locator("#addressUser").fill("Mumbai")
            return True
        except Exception: return False

    async def _screenshot(self, page: Page) -> str | None:
        try:
            png = await page.screenshot()
            return base64.b64encode(png).decode()
        except Exception: return None
