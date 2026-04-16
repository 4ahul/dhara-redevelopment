"""
MCGM Property Lookup — ArcGIS REST Client
Direct API queries against the MCGM ArcGIS feature service (fast path).
Falls back gracefully — the browser scraper is the authoritative fallback.
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MCGM_WEBAPP_ID = "3a5c0a98a75341b985c10700dec6c4b8"
MCGM_PORTAL_URL = "https://mcgm.maps.arcgis.com"

# The feature service URL discovered at runtime from the app config.
# Known pattern for MCGM ArcGIS apps: operational layers expose a REST endpoint.
# We walk the app config JSON to find the layer with WARD + FP_NO fields.
_APP_CONFIG_URL = f"{MCGM_PORTAL_URL}/sharing/rest/content/items/{MCGM_WEBAPP_ID}/data"

# Common field names we expect in the MCGM property layer
_EXPECTED_FIELDS = {"WARD", "CTS_CS_NO", "VILLAGE"}


class ArcGISClient:
    """Queries the MCGM ArcGIS feature service directly via httpx."""

    # Class-level URL cache so discovery runs only once per process lifetime.
    _layer_url: Optional[str] = None

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def discover_layer_url(self, http: httpx.AsyncClient) -> Optional[str]:
        """Fetch the ArcGIS WebApp config JSON and extract the property feature layer URL.

        The app config lists operational layers. We walk them to find the one
        containing WARD and FP_NO fields (the CTS property layer).
        """
        try:
            resp = await http.get(_APP_CONFIG_URL, params={"f": "json"}, timeout=30.0)
            resp.raise_for_status()
            config = resp.json()
        except Exception as e:
            logger.warning("Failed to fetch ArcGIS app config: %s", e)
            return None

        # Walk operational layers in the WebApp config
        op_layers = _extract_operational_layers(config)
        logger.info("Found %d operational layers in app config", len(op_layers))

        for layer_info in op_layers:
            url = layer_info.get("url", "")
            if not url:
                continue
            # Try to probe the layer's fields
            candidate = await self._probe_layer(url, http)
            if candidate:
                logger.info("Discovered property layer URL: %s", candidate)
                return candidate

        logger.warning("Could not find a matching property feature layer in app config")
        return None

    async def _probe_layer(self, layer_url: str, http: httpx.AsyncClient) -> Optional[str]:
        """Check whether a layer URL exposes WARD + FP_NO fields."""
        # Normalise: strip trailing /FeatureServer/0 variant paths for probing
        base = layer_url.rstrip("/")
        # Try the URL directly (it may already point to a specific layer index)
        try:
            resp = await http.get(base, params={"f": "json"}, timeout=15.0)
            if resp.status_code != 200:
                return None
            data = resp.json()
            fields = {f["name"] for f in data.get("fields", [])}
            if _EXPECTED_FIELDS.issubset(fields):
                return base
        except Exception as e:
            logger.debug("Layer probe failed for %s: %s", layer_url, e)

        return None

    # ── Query by CTS ─────────────────────────────────────────────────────────

    async def query_by_cts(
        self,
        ward: str,
        village: str,
        cts_no: str,
        http: httpx.AsyncClient,
    ) -> Optional[dict]:
        """Query the feature layer for a specific property."""
        layer_url = ArcGISClient._layer_url
        if not layer_url:
            # Try to discover if not cached
            layer_url = await self.discover_layer_url(http)
            if not layer_url:
                return None

        query_url = f"{layer_url}/query"

        # ── Ward Normalisation ───────────────────────────────────────────────
        ward_variants = [ward]
        w_up = ward.strip().upper()
        mapping = {
            "K/E": "K/EAST",
            "K/W": "K/WEST",
            "P/S": "P/SOUTH",
            "P/N": "P/NORTH",
            "R/S": "R/SOUTH",
            "R/C": "R/CENTRAL",
            "R/N": "R/NORTH",
            "H/E": "H/EAST",
            "H/W": "H/WEST",
        }
        if w_up in mapping:
            ward_variants.append(mapping[w_up])
        
        # ── Query Loop ───────────────────────────────────────────────────────
        for w_variant in ward_variants:
            where_clauses = []
            if w_variant:
                where_clauses.append(f"WARD='{_esc(w_variant)}'")
            if village:
                where_clauses.append(f"UPPER(VILLAGE)=UPPER('{_esc(village)}')")

            # Try CTS_CS_NO first, then FP_NO as fallback
            cts_where = " AND ".join(where_clauses + [f"CTS_CS_NO='{_esc(cts_no)}'"])
            fp_where = " AND ".join(where_clauses + [f"FP_NO='{_esc(cts_no)}'"])

            out_fields = "WARD,VILLAGE,CTS_CS_NO,TPS_NAME,FP_NO,PLOT_NO,TYPE,AREA_APP_SQ_MTRS,SHAPE.AREA,SHAPE.LEN"

            for where in [cts_where, fp_where]:
                params = {
                    "f": "json",
                    "where": where,
                    "outFields": out_fields,
                    "returnGeometry": "true",
                    "outSR": "4326",
                }

                try:
                    resp = await http.get(query_url, params=params, timeout=20.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        features = data.get("features", [])
                        if features:
                            logger.info("Direct API success for where=%s", where)
                            return features[0]
                except Exception as e:
                    logger.warning("ArcGIS variant query failed: %s", e)
                    continue

        logger.info("No features found for ward=%s village=%s cts_no=%s", ward, village, cts_no)
        return None

    # ── Nearby / Spatial query ───────────────────────────────────────────────

    async def query_nearby(
        self,
        geometry: dict,
        http: httpx.AsyncClient,
        distance_m: float = 50,
    ) -> list[dict]:
        """Find properties spatially adjacent to the given polygon.

        `geometry` is an ArcGIS geometry dict (rings in Web Mercator).
        Returns a list of ArcGIS feature dicts (without geometry for speed).
        """
        layer_url = ArcGISClient._layer_url
        if not layer_url:
            return []

        query_url = f"{layer_url}/query"

        params = {
            "f": "json",
            "geometry": json.dumps(geometry),
            "geometryType": "esriGeometryPolygon",
            "spatialRel": "esriSpatialRelIntersects",
            "distance": str(distance_m),
            "units": "esriSRUnit_Meter",
            "outFields": "WARD,TPS_NAME,FP_NO",
            "returnGeometry": "false",
            "outSR": "102100",
        }

        try:
            resp = await http.get(query_url, params=params, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("ArcGIS query_nearby failed: %s", e)
            return []

        return data.get("features", [])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _esc(s: str) -> str:
    """Escape single quotes for ArcGIS WHERE clauses."""
    return s.replace("'", "''")


def _extract_operational_layers(config: dict) -> list[dict]:
    """Recursively extract all operational layer entries from an ArcGIS app config."""
    results: list[dict] = []

    def _walk(obj):
        if isinstance(obj, dict):
            # Operational layers usually have a 'url' and 'layerType'
            if "url" in obj and obj.get("layerType") in (
                "ArcGISFeatureLayer",
                "ArcGISMapServiceLayer",
                None,  # some configs omit layerType
            ):
                results.append(obj)
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(config)
    return results
