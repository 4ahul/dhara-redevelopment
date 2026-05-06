"""
DP Report Service — ArcGIS REST Client
Queries the MCGM Development Plan 2034 feature service for DP zone data.

Follows senior developer naming standards.
"""

import asyncio
import json
import logging
import math
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# --- Constants ---

MCGM_ARCGIS_PORTAL_BASE_URL = "https://mcgm.maps.arcgis.com"

# Known Development Plan (DP) 2034 stable MapServer layers
# Layer 0 is REVISED PLU ZONES (DP 2034)
FALLBACK_DP_ZONE_LAYER_URL = (
    "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Plan_2034/MapServer/0"
)

# Field mapping sets (case-insensitive keys handled in parsing)
TARGET_ZONE_FIELDS = {"ZONE_CODE", "ZONE_CODE2", "ZONE", "LANDUSE", "LAND_USE", "DP_ZONE", "ZONING"}
TARGET_REMARK_FIELDS = {"DP_REMARKS", "DP_REMARK", "REMARKS", "REMARK", "DESCRIPTION", "DESC"}
TARGET_ROAD_WIDTH_FIELDS = {
    "ROAD_WIDTH",
    "RD_WIDTH",
    "ROAD_WID",
    "ROAD_W",
    "RD_WIDTH_M",
    "WIDTH",
    "PROPOSED_W",
}


class DevelopmentPlanArcGISClient:
    """Direct ArcGIS REST queries for MCGM DP 2034 zone data."""

    # Class-level URL caches (per process lifetime)
    _cached_zone_layer_url: str | None = None

    # --- Discovery Logic ---

    async def get_active_zone_layer_url(self, http_client: httpx.AsyncClient) -> str:
        """
        Retrieves the DP 2034 zone feature layer URL.
        Attempts discovery via portal search first, falling back to a known stable URL.
        """
        if self._cached_zone_layer_url:
            return self._cached_zone_layer_url

        search_api_url = f"{MCGM_ARCGIS_PORTAL_BASE_URL}/sharing/rest/search"
        search_queries = [
            "DP 2034 zone owner:mcgm",
            "Development Plan 2034 owner:mcgm",
            "MCGM DP zone",
        ]

        for query in search_queries:
            try:
                response = await http_client.get(
                    search_api_url,
                    params={"q": query, "f": "json", "num": 10},
                    timeout=20.0,
                )
                response.raise_for_status()
                search_results = response.json().get("results", [])

                for item in search_results:
                    item_id = item.get("id")
                    if not item_id:
                        continue
                    discovered_url = await self._probe_portal_item_for_service_url(
                        item_id, http_client
                    )
                    if discovered_url:
                        self.__class__._cached_zone_layer_url = discovered_url
                        logger.info(f"Discovered active DP zone layer: {discovered_url}")
                        return discovered_url
            except Exception as exc:
                logger.debug(f"Portal search for query '{query}' failed: {exc}")

        logger.warning(
            f"Discovery failed. Falling back to stable DP layer: {FALLBACK_DP_ZONE_LAYER_URL}"
        )
        self.__class__._cached_zone_layer_url = FALLBACK_DP_ZONE_LAYER_URL
        return FALLBACK_DP_ZONE_LAYER_URL

    async def _probe_portal_item_for_service_url(
        self, item_id: str, http_client: httpx.AsyncClient
    ) -> str | None:
        """Examines an ArcGIS portal item to find a valid feature service URL containing DP zone fields."""
        try:
            metadata_url = f"{MCGM_ARCGIS_PORTAL_BASE_URL}/sharing/rest/content/items/{item_id}"
            response = await http_client.get(metadata_url, params={"f": "json"}, timeout=15.0)
            response.raise_for_status()
            metadata = response.json()

            service_url = metadata.get("url", "")
            if not service_url:
                # Attempt to find URL in item's internal data configuration
                config_url = f"{metadata_url}/data"
                config_response = await http_client.get(
                    config_url, params={"f": "json"}, timeout=15.0
                )
                if config_response.status_code == 200:
                    service_url = (
                        _find_service_url_in_recursive_config(config_response.json()) or ""
                    )

            if not service_url:
                return None

            return await self._validate_and_extract_zone_layer_url(service_url, http_client)
        except Exception as exc:
            logger.debug(f"Probing portal item {item_id} failed: {exc}")
            return None

    async def _validate_and_extract_zone_layer_url(
        self, service_url: str, http_client: httpx.AsyncClient
    ) -> str | None:
        """Walks through available layers in a service URL to find the specific DP zone layer."""
        base_url = service_url.rstrip("/")
        try:
            response = await http_client.get(base_url, params={"f": "json"}, timeout=15.0)
            response.raise_for_status()
            service_metadata = response.json()
        except Exception:
            return None

        available_layers = service_metadata.get("layers", [])
        if not available_layers:
            # Service might be a direct layer URL
            return await self._verify_layer_has_zone_fields(base_url, http_client)

        for layer_info in available_layers:
            layer_id = layer_info.get("id", 0)
            candidate_url = f"{base_url}/{layer_id}"
            if await self._verify_layer_has_zone_fields(candidate_url, http_client):
                return candidate_url

        return None

    async def _verify_layer_has_zone_fields(
        self, layer_url: str, http_client: httpx.AsyncClient
    ) -> str | None:
        """Returns the URL if the layer's schema contains recognized DP zone fields."""
        try:
            response = await http_client.get(layer_url, params={"f": "json"}, timeout=10.0)
            if response.status_code != 200:
                return None
            layer_schema = response.json()
            field_names = {field["name"].upper() for field in layer_schema.get("fields", [])}
            if field_names & TARGET_ZONE_FIELDS:
                return layer_url
        except Exception:
            pass
        return None

    # --- Query Methods ---

    async def query_development_plan_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        http_client: httpx.AsyncClient,
    ) -> dict[str, Any] | None:
        """Identifies DP zone, road, and reservation attributes for a specific geographic point."""
        zone_layer_url = await self.get_active_zone_layer_url(http_client)
        if not zone_layer_url:
            return None

        # Determine base service URL to query neighboring layers
        service_base_url = zone_layer_url.rsplit("/", 1)[0]

        # Convert WGS84 to Web Mercator (EPSG:3857)
        merc_x, merc_y = _convert_wgs84_to_web_mercator(longitude, latitude)
        point_geometry = json.dumps(
            {"x": merc_x, "y": merc_y, "spatialReference": {"wkid": 102100}}
        )

        base_query_params = {
            "f": "json",
            "geometry": point_geometry,
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
        }

        merged_attributes: dict[str, Any] = {}

        # Layers typically indexed as: 0 (Zone), 44 (Exist Road), 45 (Prop Road), 46 (Reservations)
        # Plus common fallback IDs for road layers
        layers_to_inspect = [0, 44, 45, 46, 1128, 1527, 193, 194]

        async def fetch_layer_attributes(layer_id: int) -> dict[str, Any]:
            try:
                query_url = f"{service_base_url}/{layer_id}/query"
                layer_params = base_query_params.copy()

                # For line-based layers (roads), query an envelope/buffer to ensure intersection
                if layer_id != 0:
                    search_buffer_meters = 50.0
                    layer_params["geometry"] = json.dumps(
                        {
                            "xmin": merc_x - search_buffer_meters,
                            "ymin": merc_y - search_buffer_meters,
                            "xmax": merc_x + search_buffer_meters,
                            "ymax": merc_y + search_buffer_meters,
                            "spatialReference": {"wkid": 102100},
                        }
                    )
                    layer_params["geometryType"] = "esriGeometryEnvelope"

                response = await http_client.get(query_url, params=layer_params, timeout=15.0)
                if response.status_code == 200:
                    features = response.json().get("features", [])
                    if features:
                        # Priority check for roads: prefer features with explicit width
                        if layer_id != 0:
                            for feature in features:
                                attrs = feature.get("attributes", {})
                                for field in TARGET_ROAD_WIDTH_FIELDS:
                                    val = attrs.get(field)
                                    try:
                                        if val and float(val) > 0:
                                            return attrs
                                    except (ValueError, TypeError):
                                        continue
                        return features[0].get("attributes", {})
            except Exception as exc:
                logger.debug(f"Querying layer {layer_id} failed: {exc}")
            return {}

        results = await asyncio.gather(*(fetch_layer_attributes(lid) for lid in layers_to_inspect))
        for attribute_set in results:
            merged_attributes.update(attribute_set)

        if merged_attributes:
            logger.info(
                f"DP data merged successfully. Attribute keys: {list(merged_attributes.keys())}"
            )
            return merged_attributes

        return None

    async def query_development_plan_by_cts_number(
        self,
        ward: str,
        village: str,
        cts_number: str,
        http_client: httpx.AsyncClient,
    ) -> dict[str, Any] | None:
        """Queries the DP zone layer using CTS (Cadastral Survey) attribute matching."""
        zone_layer_url = await self.get_active_zone_layer_url(http_client)
        if not zone_layer_url:
            return None

        # Common field names for survey/CTS numbers in MCGM layers
        possible_cts_fields = ("FP_NO", "CTS_NO", "CTSR_NO", "SURVEY_NO")

        for field_name in possible_cts_fields:
            where_clause = f"UPPER({field_name}) = UPPER('{_escape_sql_string(cts_number)}')"
            try:
                response = await http_client.get(
                    f"{zone_layer_url}/query",
                    params={
                        "f": "json",
                        "where": where_clause,
                        "outFields": "*",
                        "returnGeometry": "false",
                    },
                    timeout=20.0,
                )
                if response.status_code == 200:
                    features = response.json().get("features", [])
                    if features:
                        logger.info(f"DP zone record matched via attribute '{field_name}'")
                        return features[0].get("attributes", {})
            except Exception:
                continue

        return None


# --- Attribute Parsing & Normalization ---


def normalize_development_plan_attributes(raw_attributes: dict[str, Any]) -> dict[str, Any]:
    """
    Transforms heterogeneous ArcGIS attributes into a standardized Development Plan schema.
    """
    if not raw_attributes:
        return {}

    # Case-insensitive lookup dictionary
    normalized_map = {key.upper(): val for key, val in raw_attributes.items()}

    zone_code = _extract_attribute_string(normalized_map, TARGET_ZONE_FIELDS)
    zone_description = _extract_attribute_string(
        normalized_map, {"ZONE_NAME", "ZONE_DESC", "LANDUSE_DESC", "DESCRIPTION"}
    )
    road_width_m = _extract_attribute_float(normalized_map, TARGET_ROAD_WIDTH_FIELDS)
    fsi_value = _extract_attribute_float(normalized_map, {"FSI", "FLOOR_SPACE_INDEX", "FAR"})
    height_limit_m = _extract_attribute_float(
        normalized_map, {"HEIGHT_LIMIT", "MAX_HEIGHT", "HEIGHT"}
    )

    raw_reservations = _extract_attribute_string(
        normalized_map, {"RESERVATION", "RESERVE", "RESERVED_FOR"}
    )
    dp_remarks_text = _extract_attribute_string(normalized_map, TARGET_REMARK_FIELDS)

    raw_crz_value = _extract_attribute_string(normalized_map, {"CRZ", "CRZ_ZONE", "CRZ_AREA"})
    raw_heritage_value = _extract_attribute_string(
        normalized_map, {"HERITAGE", "HERITAGE_ZONE", "HERITAGE_GRADE"}
    )

    # Parse multi-value reservations
    reservations_list = []
    if raw_reservations:
        reservations_list = [
            item.strip() for item in str(raw_reservations).split(",") if item.strip()
        ]

    return {
        "zone_code": zone_code,
        "zone_name": zone_description,
        "road_width_m": road_width_m,
        "fsi": fsi_value,
        "height_limit_m": height_limit_m,
        "reservations": reservations_list if reservations_list else None,
        "crz_zone_present": _coerce_to_boolean(raw_crz_value),
        "heritage_zone_present": _coerce_to_boolean(raw_heritage_value),
        "dp_remarks": dp_remarks_text,
    }


# --- Low-Level Utility Helpers ---


def _convert_wgs84_to_web_mercator(longitude: float, latitude: float):
    """Mathematical projection from WGS84 (lng, lat) to Web Mercator (x, y) meters."""
    EARTH_RADIUS_METERS = 6378137.0
    merc_x = EARTH_RADIUS_METERS * math.radians(longitude)
    merc_y = EARTH_RADIUS_METERS * math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2))
    return merc_x, merc_y


def _escape_sql_string(input_string: str) -> str:
    """Escapes single quotes for use in SQL-like ArcGIS where clauses."""
    return input_string.replace("'", "''")


def _extract_attribute_string(attributes_map: dict[str, Any], candidate_keys: set) -> str | None:
    """Finds the first non-empty string value for a set of candidate keys."""
    for key in candidate_keys:
        val = attributes_map.get(key)
        if val is not None:
            string_val = str(val).strip()
            if string_val not in ("", "None", "null", "NULL"):
                return string_val
    return None


def _extract_attribute_float(attributes_map: dict[str, Any], candidate_keys: set) -> float | None:
    """Finds the first valid float value for a set of candidate keys."""
    for key in candidate_keys:
        val = attributes_map.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


def _coerce_to_boolean(value: Any) -> bool | None:
    """Coerces various 'truthy' attribute values into a Python boolean."""
    if value is None:
        return None
    normalized_str = str(value).strip().upper()
    if normalized_str in ("1", "YES", "TRUE", "Y", "T"):
        return True
    if normalized_str in ("0", "NO", "FALSE", "N", "F", ""):
        return False
    return None


def _find_service_url_in_recursive_config(config_node: Any) -> str | None:
    """Recursively traverses an ArcGIS configuration structure to find a FeatureServer URL."""
    if isinstance(config_node, dict):
        url = config_node.get("url", "")
        if url and "FeatureServer" in str(url):
            return str(url)
        for child_value in config_node.values():
            result = _find_service_url_in_recursive_config(child_value)
            if result:
                return result
    elif isinstance(config_node, list):
        for item in config_node:
            result = _find_service_url_in_recursive_config(item)
            if result:
                return result
    return None
