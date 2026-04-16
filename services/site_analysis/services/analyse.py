import asyncio
import functools
import json
import logging
from typing import Optional

import googlemaps
import httpx

try:
    from core import settings
except ImportError:
    from services.site_analysis.core import settings

logger = logging.getLogger(__name__)

# MCGM DP 2034 MapServer — known working layer URLs
_MCGM_MAPSERVER = "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Plan_2034/MapServer"
_ZONE_LAYER_URL = f"{_MCGM_MAPSERVER}/0"       # REVISED PLU ZONES — has ZONE_CODE2, SUBURBS
_WARD_LAYER_URL = f"{_MCGM_MAPSERVER}/10"      # Ward Boundary — has NAME (ward code)


class SiteAnalysisUnavailableError(Exception):
    """Raised when geocoding fails entirely."""
    pass



def infer_area_type(nearby: list) -> str:
    """Infer area type from nearby places."""
    commercial_keywords = {
        "shopping", "mall", "store", "bank", "restaurant", "cafe",
        "office", "hotel", "hospital", "clinic", "pharmacy", "gym", "finance",
    }
    residential_keywords = {
        "residential", "apartment", "housing", "society", "hostel", "pg",
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
    elif commercial_score > residential_score:
        return "Predominantly Commercial"
    else:
        return "Predominantly Residential"


class SiteAnalysisService:
    """Site analysis using Google Maps API + MCGM ArcGIS for zone data."""

    def __init__(self):
        self.gmaps = None
        if settings.GOOGLE_MAPS_API_KEY:
            self.gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)

    async def analyse(
        self, address: str, ward: Optional[str] = None, plot_no: Optional[str] = None
    ) -> dict:
        """Analyze site: geocode, get nearby landmarks, query MCGM for zone."""
        geocode_result = await self._geocode(address, ward, plot_no)
        if not geocode_result:
            raise SiteAnalysisUnavailableError(
                "Geocoding failed — no API configured or all APIs errored"
            )

        lat = geocode_result["lat"]
        lng = geocode_result["lng"]

        # Query MCGM ArcGIS for real zone data
        zone_data = await self._query_mcgm_zone(lat, lng)

        return {
            "lat": lat,
            "lng": lng,
            "formatted_address": geocode_result["formatted_address"],
            "area_type": geocode_result["area_type"],
            "nearby_landmarks": geocode_result["nearby_landmarks"],
            "place_id": geocode_result["place_id"],
            "zone_inference": zone_data["zone"] if zone_data else None,
            "ward": zone_data["ward"] if zone_data else None,
            "zone_source": "mcgm_arcgis" if zone_data else "unavailable",
            "maps_url": geocode_result["maps_url"],
        }

    async def _geocode(
        self, address: str, ward: Optional[str] = None, plot_no: Optional[str] = None
    ) -> Optional[dict]:
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

                    nearby_result = await asyncio.to_thread(
                        functools.partial(
                            self.gmaps.places_nearby,
                            location=(lat, lng),
                            radius=500,
                            type="point_of_interest",
                        )
                    )

                    nearby_places = nearby_result.get("results", [])[:15]
                    landmarks = [
                        p.get("name")
                        for p in nearby_places
                        if p.get("name") and "unnamed" not in p.get("name").lower()
                    ][:6]

                    area_type = infer_area_type(nearby_places)
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={place_id}"

                    return {
                        "lat": lat,
                        "lng": lng,
                        "formatted_address": formatted_address,
                        "area_type": area_type,
                        "nearby_landmarks": landmarks,
                        "place_id": place_id,
                        "maps_url": maps_url,
                    }
            except Exception as e:
                logger.error(f"Google Maps API error: {e}")

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
                    resp = await client.get(
                        "https://serpapi.com/search", params=params
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        place_results = data.get("place_results", {})
                        if not place_results and data.get("local_results"):
                            place_results = data["local_results"][0]

                        if place_results:
                            lat = place_results.get("gps_coordinates", {}).get("latitude")
                            lng = place_results.get("gps_coordinates", {}).get("longitude")
                            formatted_address = place_results.get("address", query)
                            local_results = data.get("local_results", [])
                            landmarks = [
                                r.get("title") for r in local_results if r.get("title")
                            ][:6]

                            area_type = "Mixed Use (Residential + Commercial)"
                            if any(
                                kw in str(place_results).lower()
                                for kw in ["shop", "mall", "office"]
                            ):
                                area_type = "Predominantly Commercial"

                            return {
                                "lat": lat,
                                "lng": lng,
                                "formatted_address": formatted_address,
                                "area_type": area_type,
                                "nearby_landmarks": landmarks,
                                "place_id": place_results.get("place_id", "serp_fallback"),
                                "maps_url": place_results.get("links", {}).get(
                                    "directions",
                                    f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
                                ),
                            }
            except Exception as e:
                logger.error(f"SerpApi fallback error: {e}")

        logger.error("Both Google Maps and SerpApi failed or are unconfigured")
        return None

    async def _query_mcgm_zone(
        self, lat: float, lng: float
    ) -> Optional[dict]:
        """
        Query MCGM ArcGIS DP 2034 MapServer for ward and zone at given coordinates.
        Uses known layer URLs on agsmaps.mcgm.gov.in (the actual MCGM GIS server).
        Returns {"ward": "G/S", "zone": "R"} or None.
        """
        geometry = json.dumps(
            {"x": lng, "y": lat, "spatialReference": {"wkid": 4326}}
        )
        base_params = {
            "f": "json",
            "geometry": geometry,
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "inSR": "4326",
        }

        zone = None
        ward = None

        try:
            async with httpx.AsyncClient(timeout=20.0) as http:
                # 1. Query zone layer (REVISED PLU ZONES — layer 0)
                try:
                    resp = await http.get(
                        f"{_ZONE_LAYER_URL}/query", params=base_params
                    )
                    resp.raise_for_status()
                    features = resp.json().get("features", [])
                    if features:
                        attrs = features[0].get("attributes", {})
                        zone = attrs.get("ZONE_CODE2") or attrs.get("ZONE_CODE")
                except Exception as e:
                    logger.warning("MCGM zone layer query failed: %s", e)

                # 2. Query ward boundary layer (layer 10)
                try:
                    resp = await http.get(
                        f"{_WARD_LAYER_URL}/query", params=base_params
                    )
                    resp.raise_for_status()
                    features = resp.json().get("features", [])
                    if features:
                        attrs = features[0].get("attributes", {})
                        ward = attrs.get("NAME") or attrs.get("WARD")
                except Exception as e:
                    logger.warning("MCGM ward layer query failed: %s", e)

        except Exception as e:
            logger.warning("MCGM ArcGIS query failed: %s", e)

        if zone or ward:
            logger.info("MCGM query: ward=%s, zone=%s", ward, zone)
            return {"ward": ward, "zone": zone}

        return None


site_analysis_service = SiteAnalysisService()
