"""
CTS/FP Resolver Service
Resolves CTS (1991) ↔ FP (2034) numbers and TPS scheme using:
  1. MCGM ArcGIS API   (fast, primary)
  2. Google Gemini AI  (fallback when ArcGIS has no match)
  3. Browser scraper   (last resort — Playwright on DP sites)
"""

import json
import logging
import os
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

CTS_FP_ARCGIS_URL = "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3"

DP_2034_URL = "https://dpremarks.mcgm.gov.in/dp2034/"
DP_1991_URL = "https://dpremarks.mcgm.gov.in/srdp1991/"


@dataclass
class CTSFPResolutionResult:
    """Result of CTS/FP resolution."""
    cts_no: str | None = None
    fp_no: str | None = None
    tps_name: str | None = None
    is_validated: bool = False
    resolution_method: str = "none"
    extra: dict | None = None  # ArcGIS-sourced location metadata (ward, village, taluka, district, ...)


class CTSFPResolver:
    """Service to resolve CTS (1991) ↔ FP (2034) numbers and TPS scheme names."""

    async def resolve(
        self,
        cts_no: str | None = None,
        fp_no: str | None = None,
        ward: str | None = None,
        village: str | None = None,
        tps_name: str | None = None,
        address: str | None = None,
    ) -> CTSFPResolutionResult:
        """
        Resolve CTS ↔ FP using ArcGIS API (primary) or DP sites (fallback).

        Args:
            cts_no: CTS number (1991 scheme)
            fp_no: FP number (2034 scheme)
            ward: MCGM ward code (e.g., "H/W", "K/E")
            village: Village name (for CTS search)
            tps_name: TPS scheme name (for FP search)

        Returns:
            CTSFPResolutionResult with resolved values
        """
        result = CTSFPResolutionResult(
            cts_no=cts_no,
            fp_no=fp_no,
            tps_name=tps_name,
            is_validated=False,
            resolution_method="none",
        )

        # ── Tier 1: ArcGIS REST API (fast, authoritative) ──────────────────
        if cts_no and not fp_no:
            api_result = await self._lookup_fp_by_cts(ward, village, cts_no)
            if api_result:
                result.cts_no = cts_no
                result.fp_no = api_result.get("fp_no")
                result.tps_name = api_result.get("tps_name")
                result.is_validated = True
                result.resolution_method = "arcgis_api"
                result.extra = api_result  # carry all location fields
                return result

            # ── Tier 2: Gemini AI (knowledge-based fallback) ───────────────
            logger.info("ArcGIS had no match, trying Gemini AI fallback...")
            ai_result = await self._ai_fallback(
                cts_no=cts_no, fp_no=None, ward=ward, village=village, address=address
            )
            if ai_result and ai_result.get("tps_name"):
                result.fp_no = ai_result.get("fp_no")
                result.tps_name = ai_result.get("tps_name")
                result.is_validated = False          # AI is not authoritative
                result.resolution_method = "gemini_ai"
                return result

            # ── Tier 3: Browser scraper (last resort) ─────────────────────
            logger.info("Gemini AI fallback empty, launching browser scraper (DP 1991)...")
            fp_from_1991 = await self._get_fp_from_dp1991(ward, village, cts_no)
            if fp_from_1991 and fp_from_1991.get("fp_no"):
                result.fp_no = fp_from_1991["fp_no"]
                result.is_validated = True
                result.resolution_method = "dp_1991_scraper"
                return result

        elif fp_no and not cts_no:
            api_result = await self._lookup_cts_by_fp(ward, tps_name, fp_no)
            if api_result:
                result.fp_no = fp_no
                result.cts_no = api_result.get("cts_no")
                result.tps_name = api_result.get("tps_name")
                result.is_validated = True
                result.resolution_method = "arcgis_api"
                result.extra = api_result  # carry all location fields
                return result

            # ── Tier 2: Gemini AI ──────────────────────────────────────────
            logger.info("ArcGIS had no match, trying Gemini AI fallback...")
            ai_result = await self._ai_fallback(
                cts_no=None, fp_no=fp_no, ward=ward, village=village, address=address
            )
            if ai_result and ai_result.get("tps_name"):
                result.cts_no = ai_result.get("cts_no")
                result.tps_name = ai_result.get("tps_name")
                result.is_validated = False
                result.resolution_method = "gemini_ai"
                return result

            # ── Tier 3: Browser scraper ────────────────────────────────────
            logger.info("Gemini AI fallback empty, launching browser scraper (DP 2034)...")
            cts_from_2034 = await self._get_cts_from_dp2034(ward, village, fp_no, tps_name)
            if cts_from_2034:
                result.cts_no = cts_from_2034
                result.is_validated = True
                result.resolution_method = "dp_2034_scraper"
                return result

        return result

    # ─── Tier 2: Gemini AI fallback ──────────────────────────────────────

    async def _ai_fallback(
        self,
        cts_no: str | None,
        fp_no: str | None,
        ward: str | None,
        village: str | None,
        address: str | None,
    ) -> dict | None:
        """Use Gemini AI to infer TPS name and FP/CTS mapping when ArcGIS has no record."""
        try:
            from services.orchestrator.core.config import settings
            api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
            if not api_key:
                return None

            # Reuse the namespace-safe import helper from society_service
            import importlib
            import sys
            import sysconfig
            def _import_genai():
                try:
                    from google import genai as g
                    from google.genai import types as t
                    return g, t
                except ImportError:
                    pass
                sp = sysconfig.get_path("purelib")
                for path in [sp, "C:/Users/Admin/AppData/Local/Programs/Python/Python314/Lib/site-packages"]:
                    if path and path not in sys.path:
                        sys.path.insert(0, path)
                g = importlib.import_module("google.genai")
                t = importlib.import_module("google.genai.types")
                return g, t

            genai, gtypes = _import_genai()
            client = genai.Client(api_key=api_key)

            prompt = f"""You are a Mumbai property records expert. Given the following property details,
return ONLY a JSON object with these fields (null if unknown):
- tps_name   (TPS scheme name, e.g. "TPS IV", "TPS No. 2")
- fp_no      (FP number for this CTS under the relevant TPS)
- cts_no     (CTS number if known)

Ward: {ward or 'unknown'}
Village: {village or 'unknown'}
CTS Number: {cts_no or 'N/A'}
FP Number: {fp_no or 'N/A'}
Address: {address or 'N/A'}

Return ONLY valid JSON. No markdown, no explanation."""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=gtypes.GenerateContentConfig(temperature=0.0, max_output_tokens=256),
            )
            text = (response.text or "").strip()
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
            text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                tps = data.get("tps_name")
                if tps and str(tps).lower() not in ("null", "none", ""):
                    logger.info(f"Gemini AI resolved TPS: {tps} for CTS={cts_no} FP={fp_no}")
                    return data
        except Exception as e:
            logger.warning(f"Gemini AI fallback failed: {e}")
        return None

    # ─── Tier 1: ArcGIS API methods (primary) ────────────────────────────

    async def _lookup_fp_by_cts(
        self,
        ward: str | None,
        village: str | None,
        cts_no: str,
    ) -> dict | None:
        """Lookup FP/TPS by CTS number using ArcGIS API.

        Strategy (most precise → most permissive):
          1. CTS + VILLAGE_NAME  (village is more reliable than ward code)
          2. CTS + WARD
          3. CTS only (pick first result)
        Returns all useful location fields from the response.
        """
        if not cts_no:
            return None

        cts_clean = cts_no.strip()
        ALL_FIELDS = (
            "WARD,VILLAGE_NAME,VILLAGE,DISTRICT,TALUKA,TPS_NAME,FP_NO,"
            "CTS_CS_NO,PROPERTY_TYPE,TENURE,OWNERSHIP,AREA_IN_PRC,"
            "AREA_APP_SQ_MTRS,HOLDER_NAME,CITY_SURVEY_OFFICE"
        )

        async def _query(where: str) -> dict | None:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.get(
                        f"{CTS_FP_ARCGIS_URL}/query",
                        params={
                            "f": "json",
                            "where": where,
                            "outFields": ALL_FIELDS,
                            "returnGeometry": "false",
                            "resultRecordCount": 5,
                        },
                    )
                    feats = r.json().get("features", [])
                    return feats[0]["attributes"] if feats else None
            except Exception as e:
                logger.warning(f"ArcGIS query failed ({where[:60]}): {e}")
                return None

        attrs = None

        # Strategy 1: CTS + village name
        if village:
            v = village.replace("'", "''").upper()
            attrs = await _query(
                f"CTS_CS_NO='{cts_clean}' AND "
                f"(UPPER(VILLAGE_NAME) LIKE '%{v}%' OR UPPER(VILLAGE) LIKE '%{v}%')"
            )

        # Strategy 2: CTS + ward
        if not attrs and ward:
            attrs = await _query(f"CTS_CS_NO='{cts_clean}' AND WARD='{ward}'")

        # Strategy 3: CTS only
        if not attrs:
            attrs = await _query(f"CTS_CS_NO='{cts_clean}'")

        if not attrs:
            return None

        logger.info(
            f"ArcGIS CTS {cts_no} -> FP={attrs.get('FP_NO')}, "
            f"TPS={attrs.get('TPS_NAME')}, Ward={attrs.get('WARD')}, "
            f"Village={attrs.get('VILLAGE_NAME')}"
        )
        return {
            "fp_no":        attrs.get("FP_NO"),
            "tps_name":     attrs.get("TPS_NAME"),
            "ward":         attrs.get("WARD"),
            "village":      attrs.get("VILLAGE_NAME") or attrs.get("VILLAGE"),
            "taluka":       attrs.get("TALUKA"),
            "district":     attrs.get("DISTRICT"),
            "property_type": attrs.get("PROPERTY_TYPE"),
            "tenure":       attrs.get("TENURE"),
            "ownership":    attrs.get("OWNERSHIP"),
            "area_sqm":     attrs.get("AREA_APP_SQ_MTRS"),
            "holder_name":  attrs.get("HOLDER_NAME"),
            "city_survey_office": attrs.get("CITY_SURVEY_OFFICE"),
        }

    async def _lookup_cts_by_fp(
        self,
        ward: str | None,
        tps_name: str | None,
        fp_no: str,
    ) -> dict | None:
        """Lookup CTS by FP number using ArcGIS API.

        Strategy:
          1. FP + TPS_NAME + WARD  (most precise)
          2. FP + TPS_NAME
          3. FP only
        """
        if not fp_no:
            return None

        fp_clean = fp_no.strip()
        ALL_FIELDS = (
            "WARD,VILLAGE_NAME,VILLAGE,DISTRICT,TALUKA,TPS_NAME,FP_NO,"
            "CTS_CS_NO,PROPERTY_TYPE,TENURE,OWNERSHIP,AREA_IN_PRC,"
            "AREA_APP_SQ_MTRS,HOLDER_NAME,CITY_SURVEY_OFFICE"
        )

        async def _query(where: str) -> dict | None:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.get(
                        f"{CTS_FP_ARCGIS_URL}/query",
                        params={
                            "f": "json",
                            "where": where,
                            "outFields": ALL_FIELDS,
                            "returnGeometry": "false",
                            "resultRecordCount": 1,
                        },
                    )
                    feats = r.json().get("features", [])
                    return feats[0]["attributes"] if feats else None
            except Exception as e:
                logger.warning(f"ArcGIS query failed ({where[:60]}): {e}")
                return None

        attrs = None

        # Strategy 1: FP + TPS + ward
        if tps_name and ward:
            t = tps_name.replace("'", "''")
            attrs = await _query(f"FP_NO='{fp_clean}' AND TPS_NAME='{t}' AND WARD='{ward}'")

        # Strategy 2: FP + TPS
        if not attrs and tps_name:
            t = tps_name.replace("'", "''")
            attrs = await _query(f"FP_NO='{fp_clean}' AND TPS_NAME='{t}'")

        # Strategy 3: FP only
        if not attrs:
            attrs = await _query(f"FP_NO='{fp_clean}'")

        if not attrs:
            return None

        logger.info(
            f"ArcGIS FP {fp_no} -> CTS={attrs.get('CTS_CS_NO')}, "
            f"TPS={attrs.get('TPS_NAME')}, Ward={attrs.get('WARD')}"
        )
        return {
            "cts_no":       attrs.get("CTS_CS_NO"),
            "tps_name":     attrs.get("TPS_NAME"),
            "ward":         attrs.get("WARD"),
            "village":      attrs.get("VILLAGE_NAME") or attrs.get("VILLAGE"),
            "taluka":       attrs.get("TALUKA"),
            "district":     attrs.get("DISTRICT"),
            "property_type": attrs.get("PROPERTY_TYPE"),
            "tenure":       attrs.get("TENURE"),
            "ownership":    attrs.get("OWNERSHIP"),
            "area_sqm":     attrs.get("AREA_APP_SQ_MTRS"),
            "holder_name":  attrs.get("HOLDER_NAME"),
            "city_survey_office": attrs.get("CITY_SURVEY_OFFICE"),
        }

    # ─── DP 1991 fallback methods ─────────────────────────────────────

    async def _get_fp_from_dp1991(
        self,
        ward: str,
        village: str,
        cts_no: str,
    ) -> dict | None:
        """Get FP number from DP 1991 site using browser."""
        logger.info(f"[DP1991] Getting FP for CTS {cts_no}...")

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                await page.goto(DP_1991_URL, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(3000)

                # Fill ward
                try:
                    ward_input = page.locator('input[id*="ward"], select[id*="ward"]').first
                    await ward_input.fill(ward)
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    logger.warning(f"[DP1991] Could not fill ward: {e}")

                # Fill village
                try:
                    village_input = page.locator('input[id*="village"], select[id*="village"]').first
                    await village_input.fill(village)
                    await page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Fill CTS
                try:
                    cts_input = page.locator('input[id*="cts"], input[placeholder*="CTS"]').first
                    await cts_input.fill(cts_no)
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    logger.warning(f"[DP1991] Could not fill CTS: {e}")

                # Click search
                try:
                    search_btn = page.locator('button:has-text("Search"), input[type="submit"]').first
                    await search_btn.click()
                    await page.wait_for_timeout(5000)
                except Exception as e:
                    logger.warning(f"[DP1991] Search failed: {e}")

                # Extract FP from results
                try:
                    result_text = await page.locator('.result, table, .search-result').first.text_content()
                    if result_text:
                        fp_match = re.search(r'FP[:\s]*([0-9]+)', result_text, re.IGNORECASE)
                        if fp_match:
                            fp_no = fp_match.group(1)
                            logger.info(f"[DP1991] Found FP: {fp_no}")
                            await browser.close()
                            return {"fp_no": fp_no}
                except Exception as e:
                    logger.warning(f"[DP1991] Could not extract FP: {e}")

                logger.info(f"[DP1991] FP not found for CTS {cts_no}")
                await browser.close()
                return None

        except Exception as e:
            logger.error(f"[DP1991] Error: {e}")
            return None

    # ─── DP 2034 fallback methods ─────────────────────────────────────

    async def _get_cts_from_dp2034(
        self,
        ward: str,
        village: str,
        fp_no: str,
        tps_name: str = None,
    ) -> str | None:
        """Get CTS number from DP 2034 site using browser."""
        logger.info(f"[DP2034] Getting CTS for FP {fp_no}...")

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                await page.goto(DP_2034_URL, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(3000)

                # Click search icon
                try:
                    search_icon = page.locator('button[data-target="#searchModal"], #searchBtn').first
                    await search_icon.click()
                    await page.wait_for_timeout(2000)
                except Exception:
                    pass

                # Try FP search
                try:
                    fp_tab = page.locator('span:has-text("FP"), a:has-text("FP")').first
                    await fp_tab.click()
                    await page.wait_for_timeout(2000)
                except Exception:
                    pass

                # Fill ward
                try:
                    ward_input = page.locator('input[id*="ward"], input[placeholder*="Ward"]').first
                    await ward_input.fill(ward)
                    await page.wait_for_timeout(500)
                except Exception:
                    pass

                # Fill TPS if available
                if tps_name:
                    try:
                        tps_input = page.locator('input[id*="tps"], input[placeholder*="TPS"]').first
                        await tps_input.fill(tps_name)
                        await page.wait_for_timeout(500)
                    except Exception:
                        pass

                # Fill FP
                try:
                    fp_input = page.locator('input[id*="fp"], input[placeholder*="FP"]').first
                    await fp_input.fill(fp_no)
                    await page.wait_for_timeout(500)
                except Exception as e:
                    logger.warning(f"[DP2034] Could not fill FP: {e}")

                # Click search
                try:
                    search_btn = page.locator('button:has-text("Search"), input[type="submit"]').first
                    await search_btn.click()
                    await page.wait_for_timeout(5000)
                except Exception:
                    pass

                # Extract CTS from results
                try:
                    result_text = await page.locator('.result, table, .search-result, #result').first.text_content()
                    if result_text:
                        cts_match = re.search(r'CTS[/\s]*([0-9/]+)', result_text, re.IGNORECASE)
                        if cts_match:
                            cts = cts_match.group(1)
                            logger.info(f"[DP2034] Found CTS: {cts}")
                            await browser.close()
                            return cts
                except Exception as e:
                    logger.warning(f"[DP2034] Could not extract CTS: {e}")

                logger.info(f"[DP2034] CTS not found for FP {fp_no}")
                await browser.close()
                return None

        except Exception as e:
            logger.error(f"[DP2034] Error: {e}")
            return None


# Singleton instance
_cts_fp_resolver: CTSFPResolver | None = None


def get_resolver() -> CTSFPResolver:
    """Get singleton instance of CTSFPResolver."""
    global _cts_fp_resolver
    if _cts_fp_resolver is None:
        _cts_fp_resolver = CTSFPResolver()
    return _cts_fp_resolver



