"""
MCGM Property Lookup — Geometry Utilities
Coordinate conversion and spatial calculations.
"""

import math


def web_mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Convert Web Mercator (EPSG:3857) to WGS84 lat/lng."""
    EARTH_RADIUS = 6378137.0
    lng = (x / EARTH_RADIUS) * (180.0 / math.pi)
    lat_rad = 2 * math.atan(math.exp(y / EARTH_RADIUS)) - math.pi / 2
    lat = lat_rad * (180.0 / math.pi)
    return lat, lng


def rings_to_wgs84(rings: list) -> list:
    """Convert ArcGIS rings (Web Mercator) to WGS84 coordinate list.

    Each ring is a list of [x, y] pairs in EPSG:3857.
    Returns a flat list of [lng, lat] pairs (GeoJSON order) from the outer ring.
    """
    if not rings:
        return []
    outer_ring = rings[0]
    return [
        [round(lng, 7), round(lat, 7)]
        for x, y in outer_ring
        for lat, lng in [web_mercator_to_wgs84(x, y)]
    ]


def polygon_centroid_mercator(rings: list) -> tuple[float, float]:
    """Return centroid of the outer ring in Web Mercator."""
    ring = rings[0]
    cx = sum(p[0] for p in ring) / len(ring)
    cy = sum(p[1] for p in ring) / len(ring)
    return cx, cy


def polygon_area_sqm(rings: list) -> float:
    """Approximate area using the shoelace formula on Web Mercator coords.

    Web Mercator preserves distances poorly at high latitudes, but Mumbai
    (~18–19°N) is close enough to the equator that this gives a reasonable
    estimate in m².
    """
    ring = rings[0]
    n = len(ring)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += ring[i][0] * ring[j][1]
        area -= ring[j][0] * ring[i][1]
    return abs(area) / 2.0
