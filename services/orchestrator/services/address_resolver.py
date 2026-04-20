"""
Dhara AI — Address Resolver Service
Resolves ward, village, district, taluka from user address using web search.
"""

import logging
import re
import os
import httpx
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Mumbai ward mapping for fallback
MUMBAI_WARD_MAPPING = {
    "A": {"district": "mumbai-city", "taluka": "mumbai-city", "village": "Colaba"},
    "B": {"district": "mumbai-city", "taluka": "mumbai-city", "village": None},
    "C": {"district": "mumbai-city", "taluka": "mumbai-city", "village": None},
    "D": {"district": "mumbai-city", "taluka": "mumbai-city", "village": None},
    "E": {"district": "mumbai-city", "taluka": "mumbai-city", "village": None},
    "F/S": {"district": "mumbai-city", "taluka": "mumbai-city", "village": None},
    "F/N": {"district": "mumbai-city", "taluka": "mumbai-city", "village": None},
    "G/S": {"district": "mumbai-city", "taluka": "mumbai-city", "village": None},
    "G/N": {"district": "mumbai-city", "taluka": "mumbai-city", "village": None},
    "H/E": {"district": "mumbai-suburban", "taluka": "andheri", "village": None},
    "H/W": {"district": "mumbai-suburban", "taluka": "andheri", "village": None},
    "K/E": {
        "district": "mumbai-suburban",
        "taluka": "andheri",
        "village": "VILE PARLE",
    },
    "K/W": {
        "district": "mumbai-suburban",
        "taluka": "andheri",
        "village": "VILE PARLE",
    },
    "L": {"district": "mumbai-suburban", "taluka": "kurla", "village": None},
    "M": {"district": "mumbai-suburban", "taluka": "kurla", "village": None},
    "N": {"district": "mumbai-suburban", "taluka": "kurla", "village": None},
    "P/S": {"district": "mumbai-suburban", "taluka": "borivali", "village": None},
    "P/N": {"district": "mumbai-suburban", "taluka": "borivali", "village": None},
    "R/S": {"district": "mumbai-suburban", "taluka": "borivali", "village": None},
    "R/C": {"district": "mumbai-suburban", "taluka": "borivali", "village": None},
    "R/N": {"district": "mumbai-suburban", "taluka": "borivali", "village": None},
}


class AddressResolver:
    """Resolves ward, village, district, taluka from address using web search."""

    def __init__(self):
        self.serp_api_key = os.environ.get("SERP_API_KEY", "")
        self.serper_api_key = os.environ.get("SERPER_API_KEY", "")

    async def resolve_address(self, address: str) -> Dict[str, Optional[str]]:
        """
        Resolve address to ward, village, district, taluka.
        Returns dict with keys: ward, village, district, taluka
        """
        if not address:
            return {"ward": None, "village": None, "district": None, "taluka": None}

        # First try web search
        result = await self._search_ward_village(address)

        # If web search failed, try address parsing
        if not result.get("ward"):
            result = self._parse_address_fallback(address)

        logger.info(f"Address resolved: {address} -> {result}")
        return result

    async def _search_ward_village(self, address: str) -> Dict[str, Optional[str]]:
        """Search for ward and village using SerpApi or Serper."""

        # Try Serper first (Google search API)
        if self.serper_api_key:
            try:
                result = await self._search_serper(address)
                if result.get("ward"):
                    return result
            except Exception as e:
                logger.warning(f"Serper search failed: {e}")

        # Try SerpApi
        if self.serp_api_key:
            try:
                result = await self._search_serpapi(address)
                if result.get("ward"):
                    return result
            except Exception as e:
                logger.warning(f"SerpApi search failed: {e}")

        return {"ward": None, "village": None, "district": None, "taluka": None}

    async def _search_serper(self, address: str) -> Dict[str, Optional[str]]:
        """Search using Serper API."""
        query = f"{address} Mumbai ward village MCGM"
        url = "https://google.serper.dev/search"

        headers = {"X-API-KEY": self.serper_api_key, "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"q": query}, headers=headers)
            if response.status_code != 200:
                return {}

            data = response.json()
            return self._parse_search_results(data)

    async def _search_serpapi(self, address: str) -> Dict[str, Optional[str]]:
        """Search using SerpApi."""
        # SerpApi requires direct API call with api_key parameter
        query = f"{address} Mumbai ward village MCGM"
        url = "https://serpapi.com/search"

        params = {
            "q": query,
            "api_key": self.serp_api_key,
            "engine": "google",
            "num": 5,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return {}

            data = response.json()
            return self._parse_search_results(data)

    def _parse_search_results(self, data: dict) -> Dict[str, Optional[str]]:
        """Parse search results to extract ward and village."""

        # Look for organic results
        organic = data.get("organic_results", [])

        for result in organic:
            snippet = result.get("snippet", "") + " " + result.get("title", "")

            # Try to find ward pattern (e.g., "K/W", "K/E", "A Ward", etc.)
            ward_match = re.search(
                r"([A-Z])[/\\]?([EWNS])?\s*Ward", snippet, re.IGNORECASE
            )
            if ward_match:
                ward = ward_match.group(1)
                direction = ward_match.group(2) or ""
                ward = f"{ward}/{direction}" if direction else ward

                # Try to find village
                village_match = re.search(
                    r"village[:\s]+([A-Za-z\s]+?)(?=,|\.|$)", snippet, re.IGNORECASE
                )
                village = village_match.group(1).strip() if village_match else None

                # Get mapping info
                mapping = MUMBAI_WARD_MAPPING.get(ward.upper(), {})

                return {
                    "ward": ward.upper(),
                    "village": village or mapping.get("village"),
                    "district": mapping.get("district", "mumbai-suburban"),
                    "taluka": mapping.get("taluka", "andheri"),
                }

            # Try alternative pattern - look for CTS number with ward
            cts_ward_match = re.search(
                r"CTS?\s*No[.\s]*(\d+[A-Z]?[\d/A-Z]*).*?([A-Z])[/\\]?([EWNS])?\s*Ward",
                snippet,
                re.IGNORECASE,
            )
            if cts_ward_match:
                ward = cts_ward_match.group(2)
                direction = cts_ward_match.group(3) or ""
                ward = f"{ward}/{direction}" if direction else ward

                mapping = MUMBAI_WARD_MAPPING.get(ward.upper(), {})

                return {
                    "ward": ward.upper(),
                    "village": mapping.get("village"),
                    "district": mapping.get("district", "mumbai-suburban"),
                    "taluka": mapping.get("taluka", "andheri"),
                }

        return {"ward": None, "village": None, "district": None, "taluka": None}

    def _parse_address_fallback(self, address: str) -> Dict[str, Optional[str]]:
        """Fallback: Parse address manually for common Mumbai patterns."""
        address_lower = address.lower()

        # Extract area name
        areas = [
            "colaba",
            "fort",
            "marine lines",
            "byculla",
            "worli",
            "prabhadevi",
            "dadar",
            "parel",
            "Lower parel",
            "girgaon",
            "chowpatty",
            "walkeshwar",
            "bandra",
            "khar",
            "santacruz",
            "juhu",
            "andheri",
            "ville parle",
            " Goregaon",
            "malad",
            "borivali",
            "kandivali",
            "kurla",
            "sion",
            "chembur",
            "mulund",
            "thane",
        ]

        found_area = None
        for area in areas:
            if area in address_lower:
                found_area = area
                break

        # Map area to ward (simplified)
        area_to_ward = {
            "colaba": "A",
            "fort": "A",
            "marine lines": "A",
            "byculla": "C",
            "girgaon": "C",
            "chowpatty": "C",
            "worli": "E",
            "prabhadevi": "E",
            "parel": "E",
            "Lower parel": "E",
            "dadar": "G/S",
            "bandra": "H/W",
            "khar": "H/W",
            "santacruz": "H/W",
            "juhu": "H/W",
            "andheri": "K/E",
            "ville parle": "K/W",
            " Goregaon": "H/E",
            "malad": "R/S",
            "borivali": "P/N",
            "kandivali": "R/S",
            "kurla": "L",
            "sion": "F/N",
            "chembur": "M",
            "mulund": "N",
        }

        ward = area_to_ward.get(found_area)
        if ward:
            mapping = MUMBAI_WARD_MAPPING.get(ward, {})
            return {
                "ward": ward,
                "village": mapping.get("village"),
                "district": mapping.get("district", "mumbai-suburban"),
                "taluka": mapping.get("taluka", "andheri"),
            }

        return {"ward": None, "village": None, "district": None, "taluka": None}


# Singleton instance
address_resolver = AddressResolver()


async def resolve_address_from_input(address: str) -> Dict[str, Optional[str]]:
    """Utility function to resolve address to ward/village."""
    return await address_resolver.resolve_address(address)
