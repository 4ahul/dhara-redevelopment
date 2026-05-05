import asyncio
import functools
import json
import logging

import googlemaps
import httpx

from ..core import settings

logger = logging.getLogger(__name__)

# MCGM DP 2034 MapServer — known working layer URLs
_MCGM_MAPSERVER = "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Plan_2034/MapServer"
_ZONE_LAYER_URL = f"{_MCGM_MAPSERVER}/0"  # REVISED PLU ZONES — has ZONE_CODE2, SUBURBS
_WARD_LAYER_URL = f"{_MCGM_MAPSERVER}/10"  # Ward Boundary — has NAME (ward code)


class SiteAnalysisUnavailableError(Exception):
    """Raised when geocoding fails entirely."""


def infer_area_type(nearby: list) -> str:
    """Infer area type from nearby places."""
    commercial_keywords = {
        "shopping",
        "mall",
        "store",
        "bank",
        "restaurant",
        "cafe",
        "office",
        "hotel",
        "hospital",
        "clinic",
        "pharmacy",
        "gym",
        "finance",
    }
    residential_keywords = {
        "residential",
        "apartment",
        "housing",
        "society",
        "hostel",
        "pg",
    }

    commercial_score = 0
    residential_score = 0

    for place in nearby:
        name = place.get("name", "").lower()
        types = place.get("types", [])

        for kw in commercial_keywords:
            if kw in name:
                commercial_score += 1
                break
        for kw in residential_keywords:
            if kw in name:
                residential_score += 1
                break

        if any(t in types for t in ["store", "restaurant", "bank", "office", "health"]):
            commercial_score += 1
        if any(t in types for t in ["premise", "neighborhood", "real_estate_agency"]):
            residential_score += 0.5

    if commercial_score > 5 and residential_score > 5:
        return "Mixed Use (Residential + Commercial)"
    if commercial_score > residential_score:
        return "Predominantly Commercial"
    return "Predominantly Residential"


class SiteAnalysisService:
    """Site analysis using Google Maps API + MCGM ArcGIS for zone data."""

    def __init__(self):
        self.gmaps = None
        if settings.GOOGLE_MAPS_API_KEY:
            self.gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)

    async def analyse(
        self, address: str, ward: str | None = None, plot_no: str | None = None
    ) -> dict:
        """Analyze site: geocode, get nearby landmarks, query MCGM for zone."""
        from .storage import storage_service

        query_key = address or f"Plot {plot_no}, {ward}"

        # 1. Geocode FIRST (Sequential as it provides lat/lng and standard place_id)
        geocode_result = await self._geocode(address, ward, plot_no)
        if not geocode_result:
            raise SiteAnalysisUnavailableError(
                "Geocoding failed — no API configured or all APIs errored"
            )

        lat = geocode_result["lat"]
        lng = geocode_result["lng"]
        place_id = geocode_result.get("place_id")

        # ── Step 0: DB-First Cache Check (now using place_id) ──
        if place_id:
            cached = storage_service.get_cached_analysis(place_id)
            if cached:
                logger.info(f"Found cached site analysis for place_id: {place_id}")
                cached["is_cached"] = True
                # Echo original query key for context
                cached["query_key"] = query_key
                return cached

        # 2. Parallel Processing Block
        # We run Nearby Search and ArcGIS queries concurrently to save time
        logger.info(f"Starting parallel analysis for coords: {lat}, {lng}")

        async def get_nearby():
            if not self.gmaps:
                return [], "Predominantly Residential"
            try:
                res = await asyncio.to_thread(
                    functools.partial(
                        self.gmaps.places_nearby,
                        location=(lat, lng),
                        radius=500,
                        type="point_of_interest",
                    )
                )
                nearby_places = res.get("results", [])[:15]
                landmarks = [
                    p.get("name")
                    for p in nearby_places
                    if p.get("name") and "unnamed" not in p.get("name").lower()
                ][:6]
                area_type = infer_area_type(nearby_places)
                return landmarks, area_type
            except Exception as e:
                logger.warning(f"Nearby search failed: {e}")
                return [], "Predominantly Residential"

        # Execute parallel tasks
        nearby_task = get_nearby()
        zone_task = self._query_mcgm_zone(lat, lng)

        # asyncio.gather allows both to run simultaneously
        (landmarks, area_type), zone_data = await asyncio.gather(nearby_task, zone_task)

        result = {
            "lat": lat,
            "lng": lng,
            "formatted_address": geocode_result["formatted_address"],
            "area_type": area_type,
            "nearby_landmarks": landmarks,
            "place_id": place_id,
            "zone_inference": zone_data["zone"] if zone_data else None,
            "ward": zone_data["ward"] if zone_data else None,
            "zone_source": "mcgm_arcgis" if zone_data else "unavailable",
            "maps_url": geocode_result["maps_url"],
        }

        # Cache the result
        if place_id:
            storage_service.cache_analysis(place_id, query_key, lat, lng, result)

        return result

    async def _geocode(
        self, address: str, ward: str | None = None, plot_no: str | None = None
    ) -> dict | None:
        """Geocode address via Google Maps API or SerpApi fallback."""
        query = address or f"Plot {plot_no}, {ward}, Mumbai, India"

        # 1. Try Official Google Maps API
        if self.gmaps:
            try:
                geocode_result = await asyncio.to_thread(self.gmaps.geocode, query)
                if geocode_result:
                    result = geocode_result[0]
                    lat = result["geometry"]["location"]["lat"]
                    lng = result["geometry"]["location"]["lng"]
                    formatted_address = result.get("formatted_address", query)
                    place_id = result.get("place_id", "")

                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={place_id}"

                    return {
                        "lat": lat,
                        "lng": lng,
                        "formatted_address": formatted_address,
                        "place_id": place_id,
                        "maps_url": maps_url,
                    }
            except Exception as e:
                logger.exception(f"Google Maps API error: {e}")

        # 2. Fallback to SerpApi
        if settings.SERP_API_KEY:
            logger.info("Using SerpApi fallback for site analysis...")
            try:
                params = {
                    "engine": "google_maps",
                    "q": query,
                    "api_key": settings.SERP_API_KEY,
                    "type": "search",
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get("https://serpapi.com/search", params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        place_results = data.get("place_results", {})
                        if not place_results and data.get("local_results"):
                            place_results = data["local_results"][0]

                        if place_results:
                            lat = place_results.get("gps_coordinates", {}).get("latitude")
                            lng = place_results.get("gps_coordinates", {}).get("longitude")
                            formatted_address = place_results.get("address", query)

                            return {
                                "lat": lat,
                                "lng": lng,
                                "formatted_address": formatted_address,
                                "place_id": place_results.get("place_id", "serp_fallback"),
                                "maps_url": place_results.get("links", {}).get(
                                    "directions",
                                    f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
                                ),
                            }
            except Exception as e:
                logger.exception(f"SerpApi fallback error: {e}")

        logger.error("Both Google Maps and SerpApi failed or are unconfigured")
        return None

    async def _query_mcgm_zone(self, lat: float, lng: float) -> dict | None:
        """
        Query MCGM ArcGIS DP 2034 MapServer for ward and zone concurrently.
        """
        geometry = json.dumps(
            {"x": lng, "y": lat, "spatialReference": {"wkid": settings.ARCGIS_SR_CODE}}
        )
        base_params = {
            "f": settings.ARCGIS_FORMAT,
            "geometry": geometry,
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "inSR": str(settings.ARCGIS_SR_CODE),
        }

        async def fetch_layer(url):
            try:
                async with httpx.AsyncClient(timeout=15.0) as http:
                    resp = await http.get(f"{url}/query", params=base_params)
                    resp.raise_for_status()
                    features = resp.json().get("features", [])
                    if features:
                        return features[0].get("attributes", {})
            except Exception as e:
                logger.warning(f"MCGM query failed for {url}: {e}")
            return None

        # Execute both ArcGIS queries in parallel
        results = await asyncio.gather(fetch_layer(_ZONE_LAYER_URL), fetch_layer(_WARD_LAYER_URL))

        zone_attrs, ward_attrs = results

        zone = None
        ward = None

        if zone_attrs:
            zone = zone_attrs.get("ZONE_CODE2") or zone_attrs.get("ZONE_CODE")
        if ward_attrs:
            ward = ward_attrs.get("NAME") or ward_attrs.get("WARD")

        if zone or ward:
            logger.info("MCGM query parallel result: ward=%s, zone=%s", ward, zone)
            return {"ward": ward, "zone": zone}

        return None

    async def autocomplete(self, query: str) -> list[dict]:
        """Google Maps Places Autocomplete restricted to Mumbai."""
        if not self.gmaps:
            raise SiteAnalysisUnavailableError("Google Maps API not configured")

        try:
            res = await asyncio.to_thread(
                self.gmaps.places_autocomplete,
                input_text=query,
                location=(settings.MUMBAI_CENTER_LAT, settings.MUMBAI_CENTER_LNG),
                radius=settings.MUMBAI_RADIUS_METERS,
                strict_bounds=True,
                components={"country": "in"},
            )
            return [
                {
                    "place_id": p.get("place_id"),
                    "description": p.get("description"),
                    "main_text": p.get("structured_formatting", {}).get("main_text"),
                    "secondary_text": p.get("structured_formatting", {}).get("secondary_text"),
                }
                for p in res
                if "Mumbai" in p.get("description", "")
            ]
        except Exception as e:
            logger.exception("Google Maps Autocomplete failed: %s", e)
            raise SiteAnalysisUnavailableError(f"Autocomplete failed: {e}") from e

    async def get_place_details(self, place_id: str) -> dict:
        """Get detailed info for a specific place_id."""
        if not self.gmaps:
            raise SiteAnalysisUnavailableError("Google Maps API not configured")

        try:
            res = await asyncio.to_thread(
                self.gmaps.place,
                place_id=place_id,
                fields=["name", "formatted_address", "geometry"],
            )
            place = res.get("result", {})
            if not place:
                raise ValueError("Place not found")

            lat = place.get("geometry", {}).get("location", {}).get("lat")
            lng = place.get("geometry", {}).get("location", {}).get("lng")

            return {
                "place_id": place_id,
                "name": place.get("name"),
                "formatted_address": place.get("formatted_address"),
                "lat": lat,
                "lng": lng,
            }
        except Exception as e:
            logger.exception("Google Maps Place Details failed: %s", e)
            raise SiteAnalysisUnavailableError(f"Place Details failed: {e}") from e


site_analysis_service = SiteAnalysisService()
