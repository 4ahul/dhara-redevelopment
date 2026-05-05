"""
Wrapper for consolidated GIS metrics logic in dhara_shared.
Follows senior developer naming standards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dhara_shared.services.gis import calculate_property_gis_metrics

if TYPE_CHECKING:
    import httpx


async def calculate_property_gis_metrics_wrapper(
    property_rings_wgs84: list[list[list[float]]], http_client: httpx.AsyncClient | None = None
) -> dict:
    """Wrapper for consolidated GIS logic."""
    return await calculate_property_gis_metrics(property_rings_wgs84, http_client)


# Aliases for backward compatibility
compute_all_gis_metrics = calculate_property_gis_metrics_wrapper
