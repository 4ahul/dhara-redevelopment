import asyncio
import logging
import re
import sys
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import httpx

try:
    from core import settings
except ImportError:
    from services.height_service.core import settings

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
logger = logging.getLogger(__name__)


class HeightService:
    def __init__(self):
        self.nocas_url = "https://nocas2.aai.aero/nocas/MapPage.html"
        self.stealth = Stealth()

    def decimal_to_dms(self, decimal: float) -> tuple:
        abs_val = abs(decimal)
        dd = int(abs_val)
        mm_decimal = (abs_val - dd) * 60
        mm = int(mm_decimal)
        ss = round((mm_decimal - mm) * 60, 2)
        return dd, mm, ss

    async def _get_elevation(self, lat: float, lng: float) -> tuple:
        if settings.GOOGLE_MAPS_API_KEY:
            try:
                url = "https://maps.googleapis.com/maps/api/elevation/json"
                params = {
                    "locations": f"{lat},{lng}",
                    "key": settings.GOOGLE_MAPS_API_KEY,
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "OK" and data.get("results"):
                            return data["results"][0]["elevation"], "google"
            except Exception as e:
                logger.warning(f"Google failed: {e}")

        try:
            url = "https://api.open-meteo.com/v1/elevation"
            params = {"latitude": lat, "longitude": lng}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    elev = data.get("elevation", [])
                    if elev and len(elev) > 0:
                        return elev[0], "open_meteo"
        except Exception as e:
            logger.warning(f"Open-Meteo failed: {e}")

        return 10.0, "default"

    def _get_height_from_distance(self, lat: float, lng: float) -> float:
        """Fallback: Calculate height based on distance from Mumbai airport."""
        import math

        # Mumbai airport coordinates (Chhatrapati Shivaji Maharaj International Airport)
        AIRPORT_LAT, AIRPORT_LNG = 19.0901, 72.8659
        # Approximate distance in km using Haversine-like approximation
        distance = math.sqrt((lat - AIRPORT_LAT) ** 2 + (lng - AIRPORT_LNG) ** 2) * 111

        # AAI standard height zones:
        # 0-3km: 45m (red zone - runway approach)
        # 3-5km: 90m (orange zone)
        # 5-10km: 150m (yellow zone)
        # 10-15km: 200m (green zone)
        # 15km+: No restriction (blue zone)

        if distance <= 3:
            return 45.0
        elif distance <= 5:
            return 90.0
        elif distance <= 10:
            return 150.0
        elif distance <= 15:
            return 200.0
        return 250.0  # Default for far areas

    async def get_height(
        self, lat: float, lng: float, site_elevation: Optional[float] = None
    ) -> Dict[str, Any]:
        elevation_source = "provided"
        if site_elevation is None:
            site_elevation, elevation_source = await self._get_elevation(lat, lng)
            logger.info(f"Elevation: {site_elevation}m from {elevation_source}")

        # Step 1: Try NOCAS
        result = await self._query_nocas(lat, lng, site_elevation)

        if result:
            result["elevation_source"] = elevation_source
            result["is_real_data"] = True
            return result

        # Step 2: Try Project Maitree
        logger.info("[FALLBACK] Trying Project Maitree...")
        address = await self._get_address_from_coords(lat, lng)
        pm_result = await self._query_project_maitree(address)

        if pm_result:
            pm_result["elevation_source"] = elevation_source
            logger.info(
                f"[FALLBACK] Project Maitree found: {pm_result.get('max_height_m')}m"
            )
            return pm_result

        # Step 3: Use distance-based fallback
        fallback_height = self._get_height_from_distance(lat, lng)
        max_height = (
            fallback_height - site_elevation if site_elevation else fallback_height
        )
        logger.info(
            f"[FALLBACK] Distance-based max height: {fallback_height}m, Building: {max_height}m"
        )

        return {
            "lat": lat,
            "lng": lng,
            "site_elevation": site_elevation,
            "elevation_source": elevation_source,
            "max_height_m": round(max_height, 2),
            "max_floors": int(max_height // 3),
            "restriction_reason": f"Distance-based fallback (near Mumbai airport)",
            "nocas_reference": "Fallback",
            "aai_zone": "Mumbai Distance Fallback",
            "rl_datum_m": fallback_height,
            "is_real_data": False,
            "data_source": "distance_fallback",
            "note": "NOCAS & Maitree unavailable - used distance-based estimate",
        }

    async def _get_address_from_coords(self, lat: float, lng: float) -> str:
        """Convert lat/lng to approximate address for Maitree search."""
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"latlng": f"{lat},{lng}", "key": settings.GOOGLE_MAPS_API_KEY}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("results"):
                        return data["results"][0].get("formatted_address", "")
        except:
            pass
        return f"{lat},{lng}"

    async def _query_project_maitree(self, address: str) -> Optional[Dict[str, Any]]:
        logger.info(f"[MAITREE] Attempting...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720}
                )
                page = await context.new_page()

                await page.goto(
                    "https://www.projectmaitree.com/heightnoc", timeout=30000
                )
                await page.wait_for_load_state("networkidle", timeout=15000)
                await page.wait_for_timeout(3000)

                logger.info(f"[MAITREE] Page title: {await page.title()}")

                # Type address
                address_input = page.locator(
                    'input[type="text"], input[id*="address"], input[name*="address"]'
                ).first
                await address_input.wait_for(state="visible", timeout=10000)
                await address_input.fill(address)
                await page.wait_for_timeout(2000)

                # Click first dropdown option
                try:
                    await page.locator(
                        '.dropdown-menu li, .autocomplete li, [role="option"]'
                    ).first.click(timeout=5000)
                except Exception as e:
                    logger.warning(f"[MAITREE] Dropdown not found: {e}")

                # Click search button
                try:
                    await page.locator(
                        'button:has-text("Search"), input[type="submit"]'
                    ).first.click(timeout=5000)
                except:
                    pass

                await page.wait_for_timeout(5000)

                # Try to find results table
                try:
                    table = page.locator("table, .result, .data-table").first
                    if await table.is_visible():
                        rows = await table.locator("tr").count()
                        logger.info(f"[MAITREE] Found table with {rows} rows")
                except:
                    pass

                return None

            finally:
                await browser.close()

        return None

    async def _query_nocas(
        self, lat: float, lng: float, site_elevation: float
    ) -> Optional[Dict[str, Any]]:
        max_retries = 3
        retry_delay = 120  # 2 minutes

        for attempt in range(max_retries):
            logger.info(f"[NOCAS] Attempt {attempt + 1}/{max_retries}")
            result = await self._nocas_attempt(lat, lng, site_elevation)
            if result:
                return result

            if attempt < max_retries - 1:
                logger.info(f"[NOCAS] Site not responding, waiting {retry_delay}s before retry...")
                await asyncio.sleep(retry_delay)

        logger.warning("[NOCAS] All retries exhausted")
        return None

    async def _nocas_attempt(
        self, lat: float, lng: float, site_elevation: float
    ) -> Optional[Dict[str, Any]]:
        logger.info("[NOCAS] Starting headless browser...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()

                logger.info("[STEP 1] Loading NOCAS")
                response = await page.goto(
                    self.nocas_url, wait_until="domcontentloaded", timeout=30000
                )
                logger.info(f"[STEP 1] Response status: {response.status}")
                logger.info(f"[STEP 1] URL: {page.url}")
                await page.wait_for_timeout(3000)

                if response.status >= 400:
                    logger.warning(
                        f"[NOCAS] Site returned {response.status}, taking screenshot..."
                    )
                    await page.screenshot(path="nocas_error.png")
                    return None

                page.on(
                    "console",
                    lambda msg: logger.info(f"[BROWSER] {msg.type}: {msg.text}"),
                )

                await page.add_init_script("""
                    window.captured_alerts = [];
                    window.alert = function(msg) { window.captured_alerts.push({msg: msg}); console.log('ALERT: ' + msg); };
                """)

                logger.info("[STEP 1] Loading NOCAS")
                await page.goto(self.nocas_url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(5000)
                logger.info(f"[STEP 1] Page: {await page.title()}")

                try:
                    await page.locator('button:has-text("Accept")').click(timeout=3000)
                except:
                    pass
                try:
                    await page.locator('button:has-text("Allow")').click(timeout=3000)
                except:
                    pass

                await page.evaluate("""
                    ['popup_overlay','popup_container','terms_condition','loader'].forEach(id => {
                        const el = document.getElementById(id);
                        if(el) el.style.display = 'none';
                    });
                """)

                lat_d, lat_m, lat_s = self.decimal_to_dms(lat)
                lng_d, lng_m, lng_s = self.decimal_to_dms(lng)

                logger.info(f"[STEP 2] Filled: lat={lat}, lng={lng}, elev=0")
                await page.fill("#dy", str(lat_d))
                await page.fill("#my", str(lat_m))
                await page.fill("#sy", str(lat_s))
                await page.fill("#dx", str(lng_d))
                await page.fill("#mx", str(lng_m))
                await page.fill("#sx", str(lng_s))
                await page.fill("#site_elevation", "0")

                logger.info("[STEP 3] Clicking button...")
                try:
                    await page.locator(
                        "input[type='button'], button, [onclick*='Approx']"
                    ).first.click(timeout=5000)
                except Exception as e:
                    logger.info(
                        f"[STEP 3] Button click failed: {e}, trying evaluate..."
                    )
                    await page.evaluate("onclickApprox && onclickApprox()")

                await page.wait_for_timeout(5000)

                terms = await page.query_selector("#termsChk")
                if terms:
                    logger.info("[STEP 4] Accepting terms...")
                    await page.click("#termsChk")
                    await page.click("#btnOK")
                    await page.wait_for_timeout(3000)

                logger.info("[STEP 5] Checking for result in page...")
                for check_method in [
                    "document.getElementById('lblResult')?.innerText",
                    "document.getElementById('result')?.innerText",
                    "document.querySelector('.result')?.innerText",
                ]:
                    try:
                        result = await page.evaluate(check_method)
                        if result and len(result.strip()) > 0:
                            logger.info(f"[STEP 5] Found result: {result[:100]}")
                    except:
                        pass

                alerts = await page.evaluate("window.captured_alerts || []")
                if alerts:
                    logger.info(f"[STEP 5] Alerts captured: {alerts}")

                logger.info("[STEP 6] Waiting for result (max 60s)...")
                result_text = None
                timeout_count = 0
                retry_count = 0
                max_retries = 3

                while timeout_count < 60 and not result_text and retry_count < max_retries:
                    alerts = await page.evaluate("window.captured_alerts || []")
                    if alerts:
                        for alert in alerts:
                            msg = alert["msg"]
                            if "Approximate Permissible Top Elevation" in msg:
                                result_text = msg
                                break
                            error_keywords = ["try again", "please try", "cannot", "error", "unavailable", "failed", "timeout", "server"]
                            if any(keyword in msg.lower() for keyword in error_keywords):
                                retry_count += 1
                                logger.warning(f"[RETRY {retry_count}/{max_retries}] {msg}")
                                if retry_count < max_retries:
                                    await page.reload(wait_until="networkidle", timeout=30000)
                                    await page.wait_for_timeout(3000)
                                    await page.fill("#dy", str(lat_d))
                                    await page.fill("#my", str(lat_m))
                                    await page.fill("#sy", str(lat_s))
                                    await page.fill("#dx", str(lng_d))
                                    await page.fill("#mx", str(lng_m))
                                    await page.fill("#sx", str(lng_s))
                                    await page.fill("#site_elevation", "0")
                                    await page.evaluate("onclickApprox && onclickApprox()")
                                    timeout_count = 0
                                else:
                                    logger.warning("[RETRY] Max retries reached, giving up on NOCAS")
                                    break
                    timeout_count += 1
                    await asyncio.sleep(1)
                    if timeout_count == 10:
                        logger.info("[CHECK] Still waiting... (10s)")
                    if timeout_count == 30:
                        logger.info("[CHECK] Still waiting... (30s)")
                    if timeout_count == 45:
                        logger.info("[CHECK] Still waiting... (45s)")

                if result_text:
                    match = re.search(r"Elevation:\s*([\d\.]+)", result_text)
                    if match:
                        top_amsl = float(match.group(1))
                        max_height = top_amsl - site_elevation
                        airport = (
                            await page.evaluate("sessionStorage.getItem('Remarks')")
                            or "Unknown"
                        )
                        logger.info(f"[SUCCESS] Top: {top_amsl}m, Max: {max_height}m")
                        return {
                            "lat": lat,
                            "lng": lng,
                            "site_elevation": site_elevation,
                            "max_height_m": round(max_height, 2),
                            "max_floors": int(max_height // 3),
                            "restriction_reason": f"Airport: {airport}",
                            "nocas_reference": "Approximate",
                            "aai_zone": airport,
                            "rl_datum_m": top_amsl,
                            "data_source": "aai_nocas",
                        }

                logger.warning("[FAILED] No result")
                return None

            finally:
                await browser.close()


height_service = HeightService()
