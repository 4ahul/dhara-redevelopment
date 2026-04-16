import asyncio
import logging
import re
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)


class NOCASUnavailableError(Exception):
    """Raised when AAI NOCAS cannot be reached after retries."""
    pass


class HeightService:
    """Service to interact with AAI NOCAS Map Page to get permissible height."""

    def __init__(self):
        self.url = "https://nocas2.aai.aero/nocas/MapPage.html"
        self.stealth = Stealth()

    def decimal_to_dms(self, decimal: float) -> tuple:
        """Convert decimal degrees to DD, MM, SS."""
        abs_val = abs(decimal)
        dd = int(abs_val)
        mm_decimal = (abs_val - dd) * 60
        mm = int(mm_decimal)
        ss = round((mm_decimal - mm) * 60, 2)
        return dd, mm, ss

    async def get_height(
        self, lat: float, lng: float, site_elevation: float = 0.0
    ) -> Dict[str, Any]:
        """
        Get permissible height with retry logic. 
        Returns real data if possible, otherwise returns a safe fallback for Mumbai.
        """
        last_error = None
        for attempt in range(2):
            try:
                result = await self._fetch_from_nocas(lat, lng, site_elevation)
                if result:
                    result["is_real_data"] = True
                    result["data_source"] = "aai_nocas"
                    result["attempt"] = attempt + 1
                    return result
                last_error = "NOCAS returned no result"
            except Exception as e:
                last_error = str(e)
                logger.warning("NOCAS attempt %d/2 failed: %s", attempt + 1, e)

            if attempt < 1:
                await asyncio.sleep(2)

        # If NOCAS is down, raise NOCASUnavailableError
        logger.error("NOCAS failed after retries: %s", last_error)
        raise NOCASUnavailableError(f"AAI NOCAS Portal Unavailable: {last_error}")

    async def _fetch_from_nocas(
        self, lat: float, lng: float, site_elevation: float
    ) -> Optional[Dict[str, Any]]:
        """Single attempt to fetch height from NOCAS. Returns dict or None."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()
                await self.stealth.apply_stealth_async(page)

                page.on(
                    "console",
                    lambda msg: logger.info(f"BROWSER CONSOLE: {msg.type} {msg.text}"),
                )

                await page.add_init_script("""
                    window.captured_alerts = [];
                    let _jAlert = undefined;
                    Object.defineProperty(window, 'jAlert', {
                        get: function() { return _jAlert; },
                        set: function(newVal) {
                            _jAlert = function(msg, title, callback) {
                                window.captured_alerts.push({msg: msg});
                                console.log('NOCAS ALERT: ' + msg);
                                if (typeof callback === 'function') callback(true);
                            };
                        },
                        configurable: true
                    });
                    window.alert = function(msg) {
                        window.captured_alerts.push({msg: msg});
                        console.log('NOCAS standard ALERT: ' + msg);
                    };
                """)

                logger.info(f"Loading NOCAS page for {lat}, {lng}")
                await page.goto(self.url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(5000)

                # Clean up overlays
                await page.evaluate("""
                    const overlays = ['popup_overlay', 'popup_container', 'terms_condition', 'loader'];
                    overlays.forEach(id => {
                        const el = document.getElementById(id);
                        if (el) el.style.display = 'none';
                    });
                """)

                # Convert coords to DMS
                lat_d, lat_m, lat_s = self.decimal_to_dms(lat)
                lng_d, lng_m, lng_s = self.decimal_to_dms(lng)

                # Fill the form
                await page.fill("#dy", str(lat_d))
                await page.fill("#my", str(lat_m))
                await page.fill("#sy", str(lat_s))
                await page.fill("#dx", str(lng_d))
                await page.fill("#mx", str(lng_m))
                await page.fill("#sx", str(lng_s))
                await page.fill("#site_elevation", str(site_elevation))

                # Trigger via JS functions
                logger.info("Calling addPoint and onclickApprox via evaluate...")
                await page.evaluate("""
                    if (typeof addPoint !== 'undefined') addPoint();
                    if (typeof onclickApprox !== 'undefined') {
                        onclickApprox();
                        const btnOK = document.getElementById("btnOK");
                        if (btnOK) btnOK.click();
                    }
                """)

                # Wait for result
                logger.info("Waiting for result...")
                max_wait = 45
                result_text = None
                for _ in range(max_wait):
                    alerts = await page.evaluate("window.captured_alerts")
                    if alerts:
                        for alert in alerts:
                            msg = alert["msg"]
                            if "Approximate Permissible Top Elevation" in msg:
                                result_text = msg
                                break
                            if (
                                "cannot be determined" in msg
                                or "try later" in msg.lower()
                            ):
                                logger.warning(f"NOCAS reported error: {msg}")
                        if result_text:
                            break
                    await asyncio.sleep(1)

                if result_text:
                    match = re.search(r"Elevation:\s*([\d\.]+)", result_text)
                    if match:
                        max_height_amsl = float(match.group(1))
                        max_height_agl = max_height_amsl - site_elevation
                        airport_name = (
                            await page.evaluate(
                                "sessionStorage.getItem('Remarks')"
                            )
                            or "Unknown"
                        )

                        return {
                            "lat": lat,
                            "lng": lng,
                            "max_height_m": round(max_height_agl, 2),
                            "max_floors": int(max_height_agl // 3),
                            "restriction_reason": f"Airport proximity (Airport: {airport_name})",
                            "nocas_reference": "N/A (Approximate)",
                            "aai_zone": airport_name,
                            "rl_datum_m": max_height_amsl,
                        }

                logger.warning("No result from NOCAS on this attempt")
                return None

            finally:
                await browser.close()


height_service = HeightService()
