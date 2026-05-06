"""
Dhara AI -- Address Autocomplete Service
Uses ArcGIS World Geocoder PUBLIC API (NO API key needed), locked to Mumbai.
"""

import logging

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

ARCGIS_SUGGEST_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/suggest"
ARCGIS_FIND_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"

MUMBAI_EXTENT = "72.7,18.85,73.1,19.35"
MUMBAI_CENTER = "72.8479,19.0760"


async def suggest_addresses(text: str, max_suggestions: int = 8, category: str | None = None) -> list[dict]:
    if not text or len(text.strip()) < 2:
        return []
    params = {
        "text": text, "f": "json", "countryCode": "IND",
        "searchExtent": MUMBAI_EXTENT, "location": MUMBAI_CENTER,
        "maxSuggestions": min(max_suggestions, 15),
    }
    if category:
        params["category"] = category
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(ARCGIS_SUGGEST_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            raise HTTPException(502, f"Geocoding error: {data['error'].get('message')}")
        return [
            {"text": s.get("text", ""), "magicKey": s.get("magicKey", ""), "isCollection": s.get("isCollection", False)}
            for s in data.get("suggestions", [])
        ]
    except HTTPException:
        raise
    except httpx.TimeoutException:
        return []
    except Exception as e:
        logger.error("ArcGIS suggest failed: %s", e)
        raise HTTPException(502, f"Geocoding service error: {e}")


async def geocode_address(text: str | None = None, magic_key: str | None = None) -> dict | None:
    if not text and not magic_key:
        return None
    params = {
        "f": "json", "countryCode": "IND", "maxLocations": 1,
        "outFields": "Addr_type,StAddr,City,Region,Postal,Country,Subregion,Neighborhood",
    }
    if magic_key:
        params["magicKey"] = magic_key
    if text:
        params["SingleLine"] = text
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(ARCGIS_FIND_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return None
        c = candidates[0]
        loc, attrs = c.get("location", {}), c.get("attributes", {})
        return {
            "address": c.get("address", ""), "lat": loc.get("y"), "lng": loc.get("x"),
            "score": c.get("score"), "addressType": attrs.get("Addr_type"),
            "street": attrs.get("StAddr"), "city": attrs.get("City"),
            "subregion": attrs.get("Subregion"), "neighborhood": attrs.get("Neighborhood"),
            "region": attrs.get("Region"), "postal": attrs.get("Postal"), "country": attrs.get("Country"),
        }
    except Exception as e:
        logger.error("ArcGIS geocode failed: %s", e)
        return None
