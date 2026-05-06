"""
Geospatial calculation utilities for Dhara AI.
Consolidated from mcgm_property_lookup and dp_remarks_report.
Follows senior developer naming standards.
Requires: shapely, pyproj
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# --- Constants ---

ARCGIS_MAPSERVER_BASE_URL = (
    "https://agsmaps1.mcgm.gov.in/server/rest/services/"
    "DevelopmentPlan/Development_Plan_2034/MapServer"
)

# Known Development Plan (DP) 2034 layers
LAYER_NALLA_IDS = [110, 48, 1518, 1130, 1542]
LAYER_ROAD_IDS = [44, 45, 111, 1517]
LAYER_INDUSTRIAL_IDS = [0, 47]
LAYER_RESERVATION_IDS = [46, 107, 1540]
LAYER_ZONE_ID = 0

NALLA_KEYWORDS = (
    "nalla",
    "nallah",
    "nullah",
    "drain",
    "storm",
    "water bodies",
    "water body",
    "waterbody",
    "water",
    "watercourse",
    "stream",
    "river",
)

# --- Internal Helpers ---


def _ensure_shapely_available() -> bool:
    """Checks if shapely is installed before attempting geospatial operations."""
    try:
        import shapely  # noqa: F401

        return True
    except ImportError:
        logger.warning("Shapely library not installed. Geospatial metrics will be unavailable.")
        return False


def _convert_wgs84_to_web_mercator(rings: list) -> list:
    """Transforms coordinates from WGS84 (EPSG:4326) to Web Mercator (EPSG:3857)."""
    from pyproj import Transformer

    transformer = Transformer.from_crs(4326, 3857, always_xy=True)
    converted_rings = []
    for ring in rings:
        converted_rings.append([list(transformer.transform(pt[0], pt[1])) for pt in ring])
    return converted_rings


def _reproject_geometry(geometry, source_epsg: int = 3857, target_epsg: int = 6933):
    """Reprojects a shapely geometry between EPSG systems."""
    from pyproj import Transformer
    from shapely.ops import transform as shapely_transform

    transformer = Transformer.from_crs(source_epsg, target_epsg, always_xy=True)
    return shapely_transform(transformer.transform, geometry)


async def _fetch_arcgis_features(
    http_client: httpx.AsyncClient,
    layer_id: int,
    geometry_string: str,
    base_url: str = ARCGIS_MAPSERVER_BASE_URL,
) -> list[dict[str, Any]]:
    """Queries an ArcGIS MapServer layer for features intersecting the given geometry."""
    query_url = f"{base_url}/{layer_id}/query"
    geometry_type = (
        "esriGeometryEnvelope" if geometry_string.count(",") == 3 else "esriGeometryPolygon"
    )

    try:
        response = await http_client.get(
            query_url,
            params={
                "f": "json",
                "geometry": geometry_string,
                "geometryType": geometry_type,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "*",
                "returnGeometry": "true",
                "inSR": "102100",
                "outSR": "102100",
            },
            timeout=30.0,
        )
        return response.json().get("features", [])
    except Exception as exc:
        logger.warning(f"ArcGIS Layer {layer_id} query failed: {exc}")
        return []


def _arcgis_feature_to_shapely(feature: dict[str, Any]):
    """Converts an ArcGIS JSON feature geometry into a Shapely geometry object."""
    from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon

    geometry_data = feature.get("geometry")
    if not geometry_data:
        return None

    if "rings" in geometry_data:
        rings = geometry_data["rings"]
        if len(rings) == 1:
            return Polygon(rings[0])
        return MultiPolygon([Polygon(r) for r in rings])

    if "paths" in geometry_data:
        paths = geometry_data["paths"]
        if len(paths) == 1:
            return LineString(paths[0])
        return MultiLineString([LineString(p) for p in paths])

    return None


def _get_intersecting_polygons(geometry, target_polygon) -> list:
    """Returns a list of polygons resulting from the intersection of two geometries."""
    intersection = geometry.intersection(target_polygon)
    if intersection.is_empty:
        return []
    if intersection.geom_type == "Polygon":
        return [intersection]
    if intersection.geom_type == "MultiPolygon":
        return list(intersection.geoms)
    if intersection.geom_type == "GeometryCollection":
        return [g for g in intersection.geoms if g.geom_type == "Polygon"]
    return []


def _calculate_setback_polygon(road_line, property_polygon):
    """Builds a setback polygon based on road widening line and property boundary."""
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import linemerge, nearest_points, substring

    if road_line.geom_type == "MultiLineString":
        merged = linemerge(road_line)
        road_line = merged if merged.geom_type == "LineString" else next(iter(road_line.geoms))

    if road_line.geom_type != "LineString":
        return None

    coords = list(road_line.coords)
    if len(coords) < 2:
        return None

    boundary_line = LineString(list(property_polygon.exterior.coords))
    total_boundary_length = boundary_line.length

    point_start_on_boundary = nearest_points(property_polygon.exterior, Point(coords[0]))[0]
    point_end_on_boundary = nearest_points(property_polygon.exterior, Point(coords[-1]))[0]

    dist_start = boundary_line.project(point_start_on_boundary)
    dist_end = boundary_line.project(point_end_on_boundary)

    if abs(dist_start - dist_end) < 0.01:
        return None

    line_endpoint_1 = Point(coords[0])
    line_endpoint_2 = Point(coords[-1])

    def get_boundary_arc(start_dist, end_dist):
        if start_dist <= end_dist:
            return substring(boundary_line, start_dist, end_dist)
        segment_1 = substring(boundary_line, start_dist, total_boundary_length)
        segment_2 = substring(boundary_line, 0.0, end_dist)
        coords_1, coords_2 = list(segment_1.coords), list(segment_2.coords)
        return LineString(
            coords_1
            + (coords_2[1:] if coords_1 and coords_2 and coords_1[-1] == coords_2[0] else coords_2)
        )

    def construct_polygon(boundary_arc, is_reversed: bool):
        vertices = list(boundary_arc.coords)
        if is_reversed:
            if line_endpoint_2.distance(point_end_on_boundary) > 0.01:
                vertices.append(line_endpoint_2.coords[0])
            reversed_coords = coords[::-1]
            should_skip = Point(reversed_coords[0]).distance(Point(vertices[-1])) < 0.01
            vertices.extend(reversed_coords[1:] if should_skip else reversed_coords)
            if line_endpoint_1.distance(point_start_on_boundary) > 0.01:
                vertices.append(point_start_on_boundary.coords[0])
        else:
            if line_endpoint_1.distance(point_start_on_boundary) > 0.01:
                vertices.append(point_start_on_boundary.coords[0])
            should_skip = Point(coords[0]).distance(Point(vertices[-1])) < 0.01
            vertices.extend(coords[1:] if should_skip else coords)
            if line_endpoint_2.distance(point_end_on_boundary) > 0.01:
                vertices.append(point_end_on_boundary.coords[0])

        if Point(vertices[-1]).distance(Point(vertices[0])) > 0.01:
            vertices.append(vertices[0])

        if len(vertices) < 4:
            return None

        try:
            poly = Polygon(vertices)
            if not poly.is_valid:
                poly = poly.buffer(0)
            clipped_poly = poly.intersection(property_polygon)
            if clipped_poly.is_valid and not clipped_poly.is_empty and clipped_poly.area > 0.1:
                return clipped_poly
        except Exception:
            pass
        return None

    candidate_polygons = [
        construct_polygon(get_boundary_arc(dist_start, dist_end), True),
        construct_polygon(get_boundary_arc(dist_end, dist_start), False),
    ]
    valid_candidates = [p for p in candidate_polygons if p]

    return min(valid_candidates, key=lambda p: p.area) if valid_candidates else None


def _is_industrial_label(text_value: str) -> bool:
    """Checks if a string label indicates an industrial zone."""
    if not text_value:
        return False
    normalized_value = text_value.strip().upper()
    if "INDUSTR" in normalized_value:
        return True
    compact_value = re.sub(r"[^A-Z0-9]", "", normalized_value)
    return compact_value in {"I", "I1", "I2", "I3"}


def _match_industrial_attributes(attributes: dict[str, Any]) -> bool:
    """Checks feature attributes for any industrial classification."""
    target_keys = (
        "FINAL_DES_MAINTYPE",
        "FINAL_DES_CODE",
        "FINAL_CODE_LABEL",
        "NEW_DES_MAINTYPE_31",
        "NEW_DES_CODE_31",
        "CODE_LABEL_31",
        "DISCRIPTION",
        "REMARK",
    )
    for key in target_keys:
        value = attributes.get(key)
        if isinstance(value, str) and _is_industrial_label(value):
            return True
    for value in attributes.values():
        if isinstance(value, str) and _is_industrial_label(value):
            return True
    return False


# --- Public API ---


async def calculate_property_gis_metrics(
    property_rings_wgs84: list[list[list[float]]], http_client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """
    Computes comprehensive GIS metrics for a property polygon by querying MCGM ArcGIS layers.

    Args:
        property_rings_wgs84: List of rings, where each ring is a list of [lng, lat] coordinates.
        http_client: Optional async HTTP client for external requests.

    Returns:
        A dictionary containing calculated metrics (setback area, road width, abutting length, etc.).
    """
    if not _ensure_shapely_available() or not property_rings_wgs84:
        return {}

    from shapely.geometry import Point, Polygon
    from shapely.ops import linemerge, unary_union

    # Ensure input is in Web Mercator for ArcGIS queries
    first_coord_x = (
        property_rings_wgs84[0][0][0] if property_rings_wgs84 and property_rings_wgs84[0] else 0
    )
    if abs(first_coord_x) < 360:
        property_rings_3857 = _convert_wgs84_to_web_mercator(property_rings_wgs84)
    else:
        property_rings_3857 = property_rings_wgs84

    try:
        property_polygon = Polygon(property_rings_3857[0])
        if not property_polygon.is_valid:
            property_polygon = property_polygon.buffer(0)
    except Exception as exc:
        logger.warning(f"Failed to initialize property polygon: {exc}")
        return {}

    # Define bounding boxes for queries
    coords_x = [pt[0] for pt in property_rings_3857[0]]
    coords_y = [pt[1] for pt in property_rings_3857[0]]
    standard_bbox = (
        f"{min(coords_x) - 50},{min(coords_y) - 50},{max(coords_x) + 50},{max(coords_y) + 50}"
    )
    buffered_bbox = f"{min(coords_x) - 30.0},{min(coords_y) - 30.0},{max(coords_x) + 30.0},{max(coords_y) + 30.0}"

    own_http_client = http_client is None
    if own_http_client:
        http_client = httpx.AsyncClient(verify=False, timeout=30.0)

    metrics_result = {
        "setback_area_m2": 0.0,
        "max_road_width_m": 0.0,
        "abutting_length_m": 0.0,
        "roads_touching_count": 0,
        "carriageway_entrances_count": 0,
        "nalla_present": False,
        "industrial_present": False,
        "reservation_area_m2": 0.0,
        "zone_code": None,
        "setback_geometries": [],
        "max_road_geometries": [],
        "abutting_line_geometries": [],
    }

    try:
        # --- Metric 1: Road Setback Area ---
        property_center_y = (min(coords_y) + max(coords_y)) / 2.0
        setback_geoms_3857 = []

        # Layer 45: Proposed Road Widening (PRW)
        prw_features = await _fetch_arcgis_features(http_client, 45, standard_bbox)
        for feature in prw_features:
            road_type = (
                (feature.get("attributes", {}).get("FINAL_ROAD_TYPE2") or "").upper().strip()
            )
            if "PRW" not in road_type:
                continue
            geometry = _arcgis_feature_to_shapely(feature)
            if geometry:
                if not geometry.is_valid:
                    geometry = geometry.buffer(0)
                setback_geoms_3857.extend(_get_intersecting_polygons(geometry, property_polygon))

        # Check road widening polylines from multiple sources
        processed_lengths = set()
        widening_lines = []
        widening_sources = [
            (108, ARCGIS_MAPSERVER_BASE_URL),
            (
                32,
                "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer",
            ),
        ]

        for layer_id, base_url in widening_sources:
            features = await _fetch_arcgis_features(http_client, layer_id, buffered_bbox, base_url)
            source_segments = []
            for feature in features:
                geometry = _arcgis_feature_to_shapely(feature)
                if (
                    not geometry
                    or not geometry.is_valid
                    or geometry.geom_type not in ("LineString", "MultiLineString")
                ):
                    continue
                intersection = geometry.intersection(property_polygon)
                if not intersection.is_empty and intersection.length >= 2.0:
                    source_segments.append(intersection)

            if not source_segments:
                continue

            merged_geometry = linemerge(unary_union(source_segments))
            lines = (
                list(merged_geometry.geoms)
                if merged_geometry.geom_type == "MultiLineString"
                else [merged_geometry]
            )
            length_key = round(sum(ln.length for ln in lines), 1)

            if length_key in processed_lengths:
                continue
            processed_lengths.add(length_key)
            widening_lines.extend(lines)

            for line in lines:
                setback_poly = _calculate_setback_polygon(line, property_polygon)
                if setback_poly:
                    polygons = (
                        list(setback_poly.geoms)
                        if setback_poly.geom_type == "MultiPolygon"
                        else [setback_poly]
                    )
                    setback_geoms_3857.extend(polygons)

                # Apply 5.5m DCR buffer for certain road segments (typically north-facing in local logic)
                line_coords = list(line.coords)
                line_avg_y = sum(c[1] for c in line_coords) / len(line_coords)
                if line_avg_y > property_center_y:
                    dcr_setback_dist = 5.5
                    line_meters = _reproject_geometry(line)
                    prop_meters = _reproject_geometry(property_polygon)
                    dcr_intersection = line_meters.buffer(dcr_setback_dist).intersection(
                        prop_meters
                    )
                    if not dcr_intersection.is_empty and dcr_intersection.area > 0.1:
                        dcr_3857 = _reproject_geometry(dcr_intersection, 6933, 3857)
                        polygons = (
                            list(dcr_3857.geoms)
                            if dcr_3857.geom_type == "MultiPolygon"
                            else [dcr_3857]
                        )
                        setback_geoms_3857.extend(polygons)

        # Clip southern setbacks logic if applicable
        south_lines = [
            ln
            for ln in widening_lines
            if sum(c[1] for c in ln.coords) / len(ln.coords) <= property_center_y
        ]
        if setback_geoms_3857 and south_lines:
            endpoint_ys = [c[1] for ln in south_lines for c in list(ln.coords)[-4:]]
            if endpoint_ys:
                half_depth_limit = max(
                    0.5, (sum(endpoint_ys) / len(endpoint_ys) - min(coords_y)) / 2.0
                )
                clip_box = Polygon(
                    [
                        (min(coords_x) - 10, min(coords_y) - 10),
                        (min(coords_x) - 10, min(coords_y) + half_depth_limit),
                        (max(coords_x) + 10, min(coords_y) + half_depth_limit),
                        (max(coords_x) + 10, min(coords_y) - 10),
                    ]
                )
                setback_geoms_3857 = [
                    sb.intersection(clip_box)
                    for sb in setback_geoms_3857
                    if not sb.intersection(clip_box).is_empty
                ]

        if setback_geoms_3857:
            final_setback_union = unary_union(setback_geoms_3857)
            if not final_setback_union.is_empty:
                metrics_result["setback_area_m2"] = round(
                    _reproject_geometry(final_setback_union).area, 2
                )
                metrics_result["setback_geometries"] = (
                    list(final_setback_union.geoms)
                    if final_setback_union.geom_type == "MultiPolygon"
                    else [final_setback_union]
                )

        # --- Metric 2: Maximum Road Width ---
        dev_dept_base_url = (
            "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer"
        )
        max_detected_width = 0.0
        max_width_geometry = None
        width_data_sources = [
            (45, "WIDTH", ARCGIS_MAPSERVER_BASE_URL),  # PROPOSED_ROAD
            (33, "WIDTH", dev_dept_base_url),  # dp_roads
        ]

        for layer_id, width_field, base_url in width_data_sources:
            features = await _fetch_arcgis_features(http_client, layer_id, standard_bbox, base_url)
            for feature in features:
                width_string = str(feature.get("attributes", {}).get(width_field) or "").strip()
                if width_string:
                    numeric_matches = re.findall(r"[\d\.]+", width_string.replace(",", "."))
                    if numeric_matches:
                        width_value = float(numeric_matches[0])
                        if any(unit in width_string.upper() for unit in ("FT", "FEET")):
                            width_value *= 0.3048
                        if width_value > max_detected_width:
                            max_detected_width = width_value
                            max_width_geometry = _arcgis_feature_to_shapely(feature)

        metrics_result["max_road_width_m"] = round(max_detected_width, 2)
        if max_width_geometry and max_width_geometry.geom_type in ["Polygon", "MultiPolygon"]:
            metrics_result["max_road_geometries"] = [max_width_geometry]

        # --- Metric 3: Abutting Length and Entrances ---
        prop_poly_meters = _reproject_geometry(property_polygon, 3857, 6933)
        prop_boundary_meters = prop_poly_meters.boundary
        road_touching_keys = set()
        all_nearby_road_geoms_meters = []

        for layer_id in LAYER_ROAD_IDS:
            features = await _fetch_arcgis_features(http_client, layer_id, buffered_bbox)
            for feature in features:
                road_geom = _arcgis_feature_to_shapely(feature)
                if road_geom and road_geom.is_valid:
                    road_geom_meters = _reproject_geometry(road_geom, 3857, 6933)
                    all_nearby_road_geoms_meters.append(road_geom_meters)
                    if road_geom_meters.buffer(1.0).intersects(prop_boundary_meters):
                        bounds = road_geom_meters.bounds
                        unique_key = (
                            round(bounds[0], 1),
                            round(bounds[1], 1),
                            round(bounds[2], 1),
                            round(bounds[3], 1),
                        )
                        road_touching_keys.add(unique_key)

        if all_nearby_road_geoms_meters:
            merged_roads_buffered = unary_union(all_nearby_road_geoms_meters).buffer(1.0)
            boundary_intersection = prop_boundary_meters.intersection(merged_roads_buffered)
            if not boundary_intersection.is_empty:
                segments = []
                if boundary_intersection.geom_type == "LineString":
                    segments = [boundary_intersection]
                elif boundary_intersection.geom_type == "MultiLineString":
                    segments = [s for s in boundary_intersection.geoms if s.length > 1.0]

                if segments:
                    # Simple union-find to group contiguous segments
                    parents = list(range(len(segments)))

                    def find_parent(i):
                        while parents[i] != i:
                            parents[i] = parents[parents[i]]
                            i = parents[i]
                        return i

                    def union_groups(i, j):
                        root_i, root_j = find_parent(i), find_parent(j)
                        if root_i != root_j:
                            parents[root_j] = root_i

                    for i in range(len(segments)):
                        coords_i = list(segments[i].coords)
                        endpoints_i = [Point(coords_i[0]), Point(coords_i[-1])]
                        for j in range(i + 1, len(segments)):
                            coords_j = list(segments[j].coords)
                            endpoints_j = [Point(coords_j[0]), Point(coords_j[-1])]
                            if any(p.distance(q) <= 1.0 for p in endpoints_i for q in endpoints_j):
                                union_groups(i, j)

                    group_lengths = {}
                    group_segments = {}
                    for idx, segment in enumerate(segments):
                        root = find_parent(idx)
                        group_lengths[root] = group_lengths.get(root, 0.0) + segment.length
                        group_segments.setdefault(root, []).append(segment)

                    if group_lengths:
                        best_root = max(group_lengths, key=group_lengths.get)
                        metrics_result["abutting_length_m"] = round(group_lengths[best_root], 2)

                        longest_abutting_geometry = unary_union(group_segments[best_root])
                        if longest_abutting_geometry.geom_type == "LineString":
                            metrics_result["abutting_line_geometries"].append(
                                _reproject_geometry(longest_abutting_geometry, 6933, 3857)
                            )
                        elif longest_abutting_geometry.geom_type == "MultiLineString":
                            for part in longest_abutting_geometry.geoms:
                                metrics_result["abutting_line_geometries"].append(
                                    _reproject_geometry(part, 6933, 3857)
                                )

        metrics_result["roads_touching_count"] = len(road_touching_keys)
        metrics_result["carriageway_entrances_count"] = len(road_touching_keys) * 2

        # --- Metric 4: Nalla Presence ---
        prop_poly_buffered_1m = property_polygon.buffer(1.0)
        for layer_id in LAYER_NALLA_IDS:
            features = await _fetch_arcgis_features(http_client, layer_id, buffered_bbox)
            found_nalla = False
            for feature in features:
                geometry = _arcgis_feature_to_shapely(feature)
                if geometry and geometry.is_valid and geometry.intersects(prop_poly_buffered_1m):
                    metrics_result["nalla_present"] = True
                    found_nalla = True
                    break
            if found_nalla:
                break

        # --- Metric 5: Industrial Zone Check ---
        prop_poly_buffered_05m = property_polygon.buffer(0.5)
        for layer_id in LAYER_INDUSTRIAL_IDS:
            features = await _fetch_arcgis_features(http_client, layer_id, buffered_bbox)
            found_industrial = False
            for feature in features:
                geometry = _arcgis_feature_to_shapely(feature)
                if (
                    geometry
                    and geometry.is_valid
                    and geometry.intersects(prop_poly_buffered_05m)
                    and _match_industrial_attributes(feature.get("attributes", {}))
                ):
                    metrics_result["industrial_present"] = True
                    found_industrial = True
                    break
            if found_industrial:
                break

        # --- Metric 6: Reservation Area ---
        reservation_polygons = []
        for layer_id in LAYER_RESERVATION_IDS:
            features = await _fetch_arcgis_features(http_client, layer_id, buffered_bbox)
            for feature in features:
                geometry = _arcgis_feature_to_shapely(feature)
                if geometry and geometry.is_valid:
                    reservation_polygons.extend(
                        _get_intersecting_polygons(geometry, property_polygon)
                    )

        if reservation_polygons:
            unioned_reservation = unary_union(reservation_polygons)
            if not unioned_reservation.is_empty:
                metrics_result["reservation_area_m2"] = round(
                    _reproject_geometry(unioned_reservation, 3857, 6933).area, 2
                )

        # --- Metric 7: Zone Classification (Layer 0) ---
        zone_features = await _fetch_arcgis_features(http_client, LAYER_ZONE_ID, buffered_bbox)
        for feature in zone_features:
            geometry = _arcgis_feature_to_shapely(feature)
            if geometry and geometry.is_valid and geometry.intersects(property_polygon):
                zone_code = str((feature.get("attributes") or {}).get("ZONE_CODE2") or "").strip()
                if zone_code:
                    metrics_result["zone_code"] = zone_code
                    break

    except Exception:
        logger.exception("Error during property GIS metrics calculation")
    finally:
        if own_http_client:
            await http_client.aclose()

    return metrics_result


# Maintain backward compatibility for transition
compute_all_gis_metrics = calculate_property_gis_metrics
