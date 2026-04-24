"""
DP Report Service — ArcGIS REST Client
Queries the MCGM Development Plan 2034 feature service for DP zone data.

Strategy:
  1. Discover the DP zone feature service URL from MCGM's ArcGIS portal search.
  2. If lat/lng is provided: spatial point-in-polygon query.
  3. If only CTS/ward/village: attribute query.
  4. Return parsed DP zone attributes.
"""

import asyncio
import json
import logging
import math
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MCGM_PORTAL_URL = "https://mcgm.maps.arcgis.com"

# Fields we look for in DP zone layers (various naming conventions)
_ZONE_FIELDS = {"ZONE_CODE", "ZONE_CODE2", "ZONE", "LANDUSE", "LAND_USE", "DP_ZONE", "ZONING"}
_REMARK_FIELDS = {"DP_REMARKS", "DP_REMARK", "REMARKS", "REMARK", "DESCRIPTION", "DESC"}
_ROAD_FIELDS = {"ROAD_WIDTH", "RD_WIDTH", "ROAD_WID", "ROAD_W", "RD_WIDTH_M", "WIDTH", "PROPOSED_W"}


class DPArcGISClient:
    """Direct ArcGIS REST queries for MCGM DP 2034 zone data."""

    # Class-level URL caches (per process lifetime)
    _zone_layer_url: Optional[str] = None

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def discover_zone_layer(self, http: httpx.AsyncClient) -> Optional[str]:
        """Search MCGM's ArcGIS portal for the DP 2034 zone feature layer."""
        if DPArcGISClient._zone_layer_url:
            return DPArcGISClient._zone_layer_url

        # Search the portal for DP 2034 items
        search_url = f"{MCGM_PORTAL_URL}/sharing/rest/search"
        for query in [
            "DP 2034 zone owner:mcgm",
            "Development Plan 2034 owner:mcgm",
            "MCGM DP zone",
        ]:
            try:
                resp = await http.get(
                    search_url,
                    params={"q": query, "f": "json", "num": 10},
                    timeout=20.0,
                )
                resp.raise_for_status()
                items = resp.json().get("results", [])
                for item in items:
                    item_id = item.get("id", "")
                    if not item_id:
                        continue
                    url = await self._probe_item(item_id, http)
                    if url:
                        DPArcGISClient._zone_layer_url = url
                        logger.info("Discovered DP zone layer: %s", url)
                        return url
            except Exception as e:
                logger.debug("Portal search '%s' failed: %s", query, e)

        # ── Fallback ──────────────────────────────────────────────────────────
        # If discovery fails, use known stable DP 2034 MapServer layers
        # Layer 0 is REVISED PLU ZONES (DP 2034)
        fallback_url = "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Plan_2034/MapServer/0"
        logger.warning("Discovery failed. Using fallback DP layer: %s", fallback_url)
        DPArcGISClient._zone_layer_url = fallback_url
        return fallback_url

    async def _probe_item(self, item_id: str, http: httpx.AsyncClient) -> Optional[str]:
        """Fetch item metadata to get the feature service URL, then probe for zone fields."""
        try:
            meta_url = f"{MCGM_PORTAL_URL}/sharing/rest/content/items/{item_id}"
            resp = await http.get(meta_url, params={"f": "json"}, timeout=15.0)
            resp.raise_for_status()
            meta = resp.json()
            service_url = meta.get("url", "")
            if not service_url:
                # Try app config
                data_url = f"{meta_url}/data"
                dresp = await http.get(data_url, params={"f": "json"}, timeout=15.0)
                dresp.raise_for_status()
                config = dresp.json()
                service_url = _find_service_url_in_config(config) or ""

            if not service_url:
                return None

            # Try the service URL directly or enumerate sub-layers
            return await self._find_zone_layer_in_service(service_url, http)
        except Exception as e:
            logger.debug("Item %s probe failed: %s", item_id, e)
            return None

    async def _find_zone_layer_in_service(
        self, service_url: str, http: httpx.AsyncClient
    ) -> Optional[str]:
        """Walk FeatureServer layers to find the one with DP zone fields."""
        base = service_url.rstrip("/")
        try:
            resp = await http.get(base, params={"f": "json"}, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None

        layers = data.get("layers", [])
        if not layers:
            # Single layer — probe directly
            return await self._is_zone_layer(base, http)

        for layer in layers:
            layer_id = layer.get("id", 0)
            candidate = f"{base}/{layer_id}"
            result = await self._is_zone_layer(candidate, http)
            if result:
                return result

        return None

    async def _is_zone_layer(self, url: str, http: httpx.AsyncClient) -> Optional[str]:
        """Return the URL if this layer has DP zone fields, else None."""
        try:
            resp = await http.get(url, params={"f": "json"}, timeout=10.0)
            if resp.status_code != 200:
                return None
            data = resp.json()
            fields = {f["name"].upper() for f in data.get("fields", [])}
            if fields & _ZONE_FIELDS:
                return url
        except Exception:
            pass
        return None

    # ── Point query (lat/lng → DP zone) ──────────────────────────────────────

    async def query_by_point(
        self,
        lat: float,
        lng: float,
        http: httpx.AsyncClient,
    ) -> Optional[dict]:
        """Identify DP zone, road, and reservation data for a point."""
        layer_url = await self.discover_zone_layer(http)
        if not layer_url:
            return None

        # Base URL for other layers
        base_url = layer_url.rsplit("/", 1)[0]
        
        # Convert WGS84 to Web Mercator
        x, y = _wgs84_to_web_mercator(lng, lat)
        geometry = json.dumps({"x": x, "y": y, "spatialReference": {"wkid": 102100}})

        params = {
            "f": "json",
            "geometry": geometry,
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
        }

        merged_attrs = {}
        
        # Try Layers in priority: 0 (Zone), 44 (Exist Road), 45 (Prop Road), 46 (Reservations), 
        # 1128 (ROADS), 1527 (ROAD), 193 (Traffic RoadLines), 194 (Survey RoadLines)
        target_layers = [0, 44, 45, 46, 1128, 1527, 193, 194]
        
        async def fetch_layer(l_id):
            try:
                url = f"{base_url}/{l_id}"
                # For road/line layers, use a buffer (envelope) as they are line features
                q_params = params.copy()
                if l_id != 0:
                    # 50 meter buffer in Web Mercator to catch nearby roads
                    buffer = 50.0
                    q_params["geometry"] = json.dumps({
                        "xmin": x - buffer, "ymin": y - buffer, 
                        "xmax": x + buffer, "ymax": y + buffer,
                        "spatialReference": {"wkid": 102100}
                    })
                    q_params["geometryType"] = "esriGeometryEnvelope"
                
                resp = await http.get(f"{url}/query", params=q_params, timeout=15.0)
                if resp.status_code == 200:
                    features = resp.json().get("features", [])
                    if features:
                        # For roads, pick the one with a non-zero width if multiple exist
                        if l_id != 0:
                            for f in features:
                                attrs = f.get("attributes", {})
                                for k in _ROAD_FIELDS:
                                    val = attrs.get(k)
                                    try:
                                        if val and float(val) > 0:
                                            return attrs
                                    except (ValueError, TypeError):
                                        continue
                        return features[0].get("attributes", {})
            except Exception as e:
                logger.debug("Querying layer %d failed: %s", l_id, e)
            return {}

        results = await asyncio.gather(*(fetch_layer(lid) for lid in target_layers))
        for attr_set in results:
            merged_attrs.update(attr_set)

        if merged_attrs:
            logger.info("DP data merged from multiple layers. Keys: %s", list(merged_attrs.keys()))
            logger.info("Merged attributes: %s", json.dumps(merged_attrs))
            return merged_attrs

        return None

    # ── CTS attribute query ───────────────────────────────────────────────────

    async def query_by_cts(
        self,
        ward: str,
        village: str,
        cts_no: str,
        http: httpx.AsyncClient,
    ) -> Optional[dict]:
        """Query DP zone by CTS/ward attribute."""
        layer_url = await self.discover_zone_layer(http)
        if not layer_url:
            return None

        # Try various CTS field name conventions
        for cts_field in ("FP_NO", "CTS_NO", "CTSR_NO", "SURVEY_NO"):
            where = f"UPPER({cts_field}) = UPPER('{_esc(cts_no)}')"
            try:
                resp = await http.get(
                    f"{layer_url}/query",
                    params={
                        "f": "json",
                        "where": where,
                        "outFields": "*",
                        "returnGeometry": "false",
                    },
                    timeout=20.0,
                )
                if resp.status_code == 200:
                    features = resp.json().get("features", [])
                    if features:
                        logger.info("DP zone found via CTS attribute query")
                        return features[0].get("attributes", {})
            except Exception:
                continue

        return None


# ── Attribute parsing ─────────────────────────────────────────────────────────


def parse_dp_attributes(attrs: dict) -> dict:
    """
    Normalise raw ArcGIS attributes into a clean DP remarks dict.
    Handles various MCGM field naming conventions.
    """
    if not attrs:
        return {}

    up = {k.upper(): v for k, v in attrs.items()}

    zone_code = _pick(up, _ZONE_FIELDS)
    zone_name = _pick(up, {"ZONE_NAME", "ZONE_DESC", "LANDUSE_DESC", "DESCRIPTION"})
    road_width = _pick_float(up, _ROAD_FIELDS)
    fsi = _pick_float(up, {"FSI", "FLOOR_SPACE_INDEX", "FAR"})
    height = _pick_float(up, {"HEIGHT_LIMIT", "MAX_HEIGHT", "HEIGHT"})
    reservations_raw = _pick(up, {"RESERVATION", "RESERVE", "RESERVED_FOR"})
    dp_remarks = _pick(up, _REMARK_FIELDS)
    crz_raw = _pick(up, {"CRZ", "CRZ_ZONE", "CRZ_AREA"})
    heritage_raw = _pick(up, {"HERITAGE", "HERITAGE_ZONE", "HERITAGE_GRADE"})

    reservations = []
    if reservations_raw:
        reservations = [r.strip() for r in str(reservations_raw).split(",") if r.strip()]

    crz_zone = _truthy(crz_raw)
    heritage_zone = _truthy(heritage_raw)

    return {
        "zone_code": zone_code,
        "zone_name": zone_name,
        "road_width_m": road_width,
        "fsi": fsi,
        "height_limit_m": height,
        "reservations": reservations if reservations else None,
        "crz_zone": crz_zone,
        "heritage_zone": heritage_zone,
        "dp_remarks": dp_remarks,
    }


# ── Utilities ─────────────────────────────────────────────────────────────────


def _wgs84_to_web_mercator(lng: float, lat: float):
    """Convert WGS84 (lng, lat) → Web Mercator (x, y) in metres."""
    R = 6378137.0
    x = R * math.radians(lng)
    y = R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def _esc(s: str) -> str:
    return s.replace("'", "''")


def _pick(up: dict, keys: set) -> Optional[str]:
    for k in keys:
        v = up.get(k)
        if v is not None and str(v).strip() not in ("", "None", "null"):
            return str(v).strip()
    return None


def _pick_float(up: dict, keys: set) -> Optional[float]:
    for k in keys:
        v = up.get(k)
        if v is not None:
            try:
                return float(v)
            except (ValueError, TypeError):
                continue
    return None


def _truthy(val) -> Optional[bool]:
    if val is None:
        return None
    s = str(val).strip().upper()
    if s in ("1", "YES", "TRUE", "Y"):
        return True
    if s in ("0", "NO", "FALSE", "N", ""):
        return False
    return None


def _find_service_url_in_config(config: dict) -> Optional[str]:
    """Recursively find a feature service URL in an ArcGIS app config."""
    if isinstance(config, dict):
        url = config.get("url", "")
        if url and "FeatureServer" in str(url):
            return str(url)
        for v in config.values():
            result = _find_service_url_in_config(v)
            if result:
                return result
    elif isinstance(config, list):
        for item in config:
            result = _find_service_url_in_config(item)
            if result:
                return result
    return None

