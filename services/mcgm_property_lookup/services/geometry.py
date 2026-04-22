"""
MCGM Property Lookup — Geometry Utilities
Coordinate conversion and spatial calculations.
"""

import geopandas as gpd
from shapely.geometry import Polygon

def web_mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Convert Web Mercator (EPSG:3857) to WGS84 lat/lng using GeoPandas."""
    gdf = gpd.GeoDataFrame(geometry=gpd.points_from_xy([x], [y]), crs="EPSG:3857")
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    point = gdf_wgs84.geometry.iloc[0]
    return point.y, point.x

def rings_to_wgs84(rings: list) -> list:
    """Convert ArcGIS rings (Web Mercator) to WGS84 coordinate list.
    Returns a flat list of [lng, lat] pairs from the outer ring.
    """
    if not rings:
        return []
    outer_ring = rings[0]
    # Create Polygon in Web Mercator and transform
    poly = Polygon(outer_ring)
    gdf = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:3857")
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    
    transformed_poly = gdf_wgs84.geometry.iloc[0]
    return [[round(lng, 7), round(lat, 7)] for lng, lat in transformed_poly.exterior.coords]

def polygon_centroid_mercator(rings: list) -> tuple[float, float]:
    """Return centroid of the outer ring in Web Mercator using GeoPandas."""
    if not rings:
        return 0.0, 0.0
    poly = Polygon(rings[0])
    gdf = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:3857")
    centroid = gdf.geometry.centroid.iloc[0]
    return centroid.x, centroid.y

def polygon_area_sqm(rings: list) -> float:
    """Accurately calculate area using equal-area projections natively in GeoPandas.
    Projects EPSG:3857 -> EPSG:6933 (Cylindrical Equal Area) -> measures exact m².
    """
    if not rings:
        return 0.0
    poly = Polygon(rings[0])
    # Original is Web Mercator
    gdf = gpd.GeoDataFrame(geometry=[poly], crs="EPSG:3857")
    # Reproject to a global equal area projection (EPSG:6933) for accurate area
    gdf_equal_area = gdf.to_crs(epsg=6933)
    
    return float(gdf_equal_area.geometry.area.iloc[0])
