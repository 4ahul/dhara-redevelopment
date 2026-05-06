"""
Wrapper for consolidated GIS metrics logic in dhara_shared.
Follows senior developer naming standards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dhara_shared.services.gis import calculate_property_gis_metrics

if TYPE_CHECKING:
    import httpx


async def compute_setback_area(
    geometry_wgs84: list[list[float]],
    http_client: httpx.AsyncClient | None = None,
) -> float:
    """
    Computes setback (road widening) area in m2 using consolidated GIS logic.
    """
    # Ensure input is formatted as a list of rings (list of list of list of floats)
    if geometry_wgs84 and not isinstance(geometry_wgs84[0][0], (list, tuple)):
        property_rings = [geometry_wgs84]
    else:
        property_rings = geometry_wgs84

    metrics = await calculate_property_gis_metrics(property_rings, http_client)
    return metrics.get("setback_area_m2", 0.0)
