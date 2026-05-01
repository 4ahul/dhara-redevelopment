import os
import asyncio
import json
import httpx
import re
import importlib.util
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point, shape
import urllib3
urllib3.disable_warnings()

# Load visualization directly
spec = importlib.util.spec_from_file_location(
    "visualization",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "services/mcgm_property_lookup/services/visualization.py")
)
vis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vis)
generate_plot_map = vis.generate_plot_map

# Load geometry for area
spec2 = importlib.util.spec_from_file_location(
    "geometry",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "services/mcgm_property_lookup/services/geometry.py")
)
geo = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(geo)

# ==============================================================================
# Search Parameters
# ==============================================================================
MODE = "FP"   # "CTS" or "FP"

WARD      = "K/W"
VILLAGE   = ""
CTS_NO    = ""

TPS_NAME  = "TPS VILE PARLE NO VI"
FP_NO     = "52"
# Known DP Remarks layers for nallas/water bodies
NALLA_LAYER_IDS = [110, 48, 1518, 1130, 1542]
# Known DP Remarks layers for roads (existing/proposed/TPS)
ROAD_LAYER_IDS = [44, 45, 111, 1517]
# Layer 44 = EXISTING_ROAD (light green on DP map), Layer 45 = PROPOSED_ROAD (dark green/orange-brown)
ROAD_AREA_LAYER_IDS = [44, 45]
# DP Remarks layers used to detect Industrial zones
INDUSTRIAL_LAYER_IDS = [0, 47]
# DP Remarks layers used to compute reservation area
RESERVATION_LAYER_IDS = [46, 107, 1540]
# Layer 0 = REVISED PLU ZONES; ZONE_CODE2 field stores R, C, I, NA, NDZ, SDZ etc.
ZONE_LAYER_ID = 0
WHITE_ZONE_CODES   = ["R"]
LIGHT_GREEN_CODES  = ["NA"]
DARK_GREEN_CODES   = ["NDZ", "SDZ", "NDZ/SDZ", "NDZ/SDZ (Slum)"]
NALLA_KEYWORDS = (
    "nalla", "nallah", "nullah", "drain", "storm",
    "water bodies", "water body", "waterbody",
    "water", "watercourse", "stream", "river",
)
# ==============================================================================
from shapely.ops import linemerge, unary_union, nearest_points as shapely_nearest_points, substring as shapely_substring

def get_layer_url():
    if MODE == "CTS":
        return "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/2"
    return "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3"

DP_REMARKS_BASE_URL = "https://agsmaps1.mcgm.gov.in/server/rest/services/DevelopmentPlan/Development_Plan_2034/MapServer"

def _project_to_meters(geom, src_epsg=3857, dst_epsg=6933):
    gdf = gpd.GeoDataFrame(geometry=[geom], crs=f"EPSG:{src_epsg}")
    return gdf.to_crs(epsg=dst_epsg).geometry.iloc[0]


async def fetch_intersecting_features(http, layer_id, geom_str, base_url=None):
    base = base_url or "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer"
    url = f"{base}/{layer_id}/query"
    try:
        geom_type = "esriGeometryEnvelope" if "," in geom_str and geom_str.count(",") == 3 else "esriGeometryPolygon"
        resp = await http.get(url, params={
            "f": "json", "geometry": geom_str, "geometryType": geom_type,
            "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true",
            "inSR": "102100", "outSR": "102100"
        }, timeout=30.0)
        data = resp.json()
        return data.get("features", [])
    except Exception as e:
        print(f"Error fetching layer {layer_id}: {e}")
        return []

async def find_layer_ids_by_name(http, base_url, keywords):
    try:
        resp = await http.get(base_url, params={"f": "json"}, timeout=30.0)
        data = resp.json()
    except Exception as e:
        print(f"Error fetching layers from {base_url}: {e}")
        return []

    layers = (data.get("layers") or []) + (data.get("tables") or [])
    matched = []
    for layer in layers:
        name = (layer.get("name") or "").lower()
        if any(kw in name for kw in keywords):
            layer_id = layer.get("id")
            if layer_id is not None:
                matched.append(layer_id)

    seen = set()
    ordered = []
    for layer_id in matched:
        if layer_id in seen:
            continue
        seen.add(layer_id)
        ordered.append(layer_id)
    return ordered

def extract_shapely_geom(feature):
    geom = feature.get("geometry")
    if not geom: return None
    if "rings" in geom:
        rings = geom["rings"]
        if len(rings) == 1: return Polygon(rings[0])
        else: return MultiPolygon([Polygon(r) for r in rings])
    elif "paths" in geom:
        paths = geom["paths"]
        if len(paths) == 1:
            return LineString(paths[0])
        return MultiLineString([LineString(p) for p in paths])
    return None

def build_where_clause() -> str:
    if MODE == "CTS":
        return f"WARD='{WARD}' AND UPPER(VILLAGE_NAME) LIKE UPPER('%{VILLAGE}%') AND CTS_CS_NO='{CTS_NO}'"
    return f"WARD='{WARD}' AND UPPER(TPS_NAME) LIKE UPPER('%VILE PARLE No.VI%') AND FP_NO='{FP_NO}'"

def _is_industrial_value(value: str) -> bool:
    if not value:
        return False
    v = value.strip().upper()
    if "INDUSTR" in v:
        return True
    v_compact = re.sub(r"[^A-Z0-9]", "", v)
    return v_compact in {"I", "I1", "I2", "I3"}

def _attrs_match_industrial(attrs: dict) -> bool:
    for key in (
        "FINAL_DES_MAINTYPE", "FINAL_DES_CODE", "FINAL_CODE_LABEL",
        "NEW_DES_MAINTYPE_31", "NEW_DES_CODE_31", "CODE_LABEL_31",
        "DISCRIPTION", "REMARK",
    ):
        val = attrs.get(key)
        if isinstance(val, str) and _is_industrial_value(val):
            return True
    for val in attrs.values():
        if isinstance(val, str) and _is_industrial_value(val):
            return True
    return False

def _boundary_anchor(endpoint_coord, boundary):
    return shapely_nearest_points(boundary, Point(endpoint_coord))[0]


def _build_setback_polygon(line, prop_poly):
    if line.geom_type == "MultiLineString":
        merged = linemerge(line)
        line = merged if merged.geom_type == "LineString" else list(line.geoms)[0]
    if line.geom_type != "LineString":
        return None
    coords_line = list(line.coords)
    if len(coords_line) < 2:
        return None

    boundary = prop_poly.exterior
    boundary_ls = LineString(list(boundary.coords))
    total_len = boundary_ls.length

    B1 = _boundary_anchor(coords_line[0],  boundary)
    B2 = _boundary_anchor(coords_line[-1], boundary)

    P1, P2 = Point(coords_line[0]), Point(coords_line[-1])
    d1 = boundary_ls.project(B1)
    d2 = boundary_ls.project(B2)
    if abs(d1 - d2) < 0.01:
        return None

    def arc_fwd(s, e):
        if s <= e:
            return shapely_substring(boundary_ls, s, e)
        seg1 = shapely_substring(boundary_ls, s, total_len)
        seg2 = shapely_substring(boundary_ls, 0.0, e)
        c1, c2 = list(seg1.coords), list(seg2.coords)
        return LineString(c1 + (c2[1:] if c1 and c2 and c1[-1] == c2[0] else c2))

    def build_poly(arc, bridge_end_is_B2):
        verts = list(arc.coords)
        if bridge_end_is_B2:
            if P2.distance(B2) > 0.01:
                verts.append(P2.coords[0])
            line_rev = coords_line[::-1]
            skip = Point(line_rev[0]).distance(Point(verts[-1])) < 0.01
            verts.extend(line_rev[1:] if skip else line_rev)
            if P1.distance(B1) > 0.01:
                verts.append(B1.coords[0])
        else:
            if P1.distance(B1) > 0.01:
                verts.append(P1.coords[0])
            skip = Point(coords_line[0]).distance(Point(verts[-1])) < 0.01
            verts.extend(coords_line[1:] if skip else coords_line)
            if P2.distance(B2) > 0.01:
                verts.append(B2.coords[0])
        if Point(verts[-1]).distance(Point(verts[0])) > 0.01:
            verts.append(verts[0])
        if len(verts) < 4:
            return None
        try:
            poly = Polygon(verts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            poly = poly.intersection(prop_poly)
            if poly.is_valid and not poly.is_empty and poly.area > 0.1:
                return poly
        except Exception:
            pass
        return None

    arc_AB = arc_fwd(d1, d2)
    arc_BA = arc_fwd(d2, d1)

    cand1 = build_poly(arc_AB, bridge_end_is_B2=True)
    cand2 = build_poly(arc_BA, bridge_end_is_B2=False)

    candidates = [c for c in [cand1, cand2] if c is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda p: p.area)

def _collect_intersection_polys(geom, prop_poly):
    inter = geom.intersection(prop_poly)
    if inter.is_empty:
        return []
    if inter.geom_type == "Polygon":
        return [inter]
    if inter.geom_type == "MultiPolygon":
        return list(inter.geoms)
    if inter.geom_type == "GeometryCollection":
        return [g for g in inter.geoms if g.geom_type == "Polygon"]
    return []

async def area_from_layers(http, layer_ids, prop_poly, buffered_geom_str) -> float:
    polys = []
    for layer_id in layer_ids:
        feats = await fetch_intersecting_features(http, layer_id, buffered_geom_str, base_url=DP_REMARKS_BASE_URL)
        for feat in feats:
            geom = extract_shapely_geom(feat)
            if not geom or not geom.is_valid:
                continue
            polys.extend(_collect_intersection_polys(geom, prop_poly))

    if not polys:
        return 0.0

    unioned = unary_union(polys)
    if unioned.is_empty:
        return 0.0
    return _project_to_meters(unioned, 3857, 6933).area

async def area_from_zone_codes(http, zone_codes, prop_poly, buffered_geom_str) -> float:
    feats = await fetch_intersecting_features(http, ZONE_LAYER_ID, buffered_geom_str, base_url=DP_REMARKS_BASE_URL)
    codes_upper = {c.upper().strip() for c in zone_codes}
    polys = []
    for feat in feats:
        code = feat.get("attributes", {}).get("ZONE_CODE2", "") or ""
        if code.upper().strip() not in codes_upper:
            continue
        geom = extract_shapely_geom(feat)
        if not geom or not geom.is_valid:
            continue
        polys.extend(_collect_intersection_polys(geom, prop_poly))
    if not polys:
        return 0.0
    unioned = unary_union(polys)
    if unioned.is_empty:
        return 0.0
    return _project_to_meters(unioned, 3857, 6933).area

async def detect_nalla(http, prop_poly, buffered_geom_str) -> bool:
    prop_poly_buf = prop_poly.buffer(1.0)

    for layer_id in NALLA_LAYER_IDS:
        feats = await fetch_intersecting_features(http, layer_id, buffered_geom_str, base_url=DP_REMARKS_BASE_URL)
        for feat in feats:
            geom = extract_shapely_geom(feat)
            if geom and geom.is_valid and geom.intersects(prop_poly_buf):
                return True

    layer_ids = await find_layer_ids_by_name(http, DP_REMARKS_BASE_URL, NALLA_KEYWORDS)
    for layer_id in layer_ids:
        feats = await fetch_intersecting_features(http, layer_id, buffered_geom_str, base_url=DP_REMARKS_BASE_URL)
        for feat in feats:
            geom = extract_shapely_geom(feat)
            if geom and geom.is_valid and geom.intersects(prop_poly_buf):
                return True
    return False

async def detect_industrial(http, prop_poly, buffered_geom_str) -> bool:
    prop_poly_buf = prop_poly.buffer(0.5)
    for layer_id in INDUSTRIAL_LAYER_IDS:
        feats = await fetch_intersecting_features(http, layer_id, buffered_geom_str, base_url=DP_REMARKS_BASE_URL)
        for feat in feats:
            geom = extract_shapely_geom(feat)
            if not geom or not geom.is_valid or not geom.intersects(prop_poly_buf):
                continue
            attrs = feat.get("attributes", {})
            if _attrs_match_industrial(attrs):
                return True
    return False

async def test_lookup_and_draw():
    where = build_where_clause()
    print(f"Search Mode : {MODE}")
    print(f"WHERE clause: {where}\n")

    async with httpx.AsyncClient(verify=False) as http:
        layer_url = get_layer_url()
        resp = await http.get(f"{layer_url}/query", params={
            "f": "json", "where": where, "outFields": "*", "returnGeometry": "true", "outSR": "102100",
        }, timeout=30.0)
        data = resp.json()

        features = data.get("features", [])
        if not features:
            print("Property not found.")
            return

        feature = features[0]
        attrs = feature.get("attributes", {})
        rings = feature.get("geometry", {}).get("rings", [])

        print(f"Property Found!")
        print(f"   Ward:       {attrs.get('WARD')}")
        print(f"   TPS Name:   {attrs.get('TPS_NAME')}")
        print(f"   FP No:      {attrs.get('FP_NO')}")

        area = geo.polygon_area_sqm(rings)
        print(f"   Total Area: {area:.2f} m²")

        try:
            prop_poly = Polygon(rings[0])
            prop_poly_m = _project_to_meters(prop_poly, 3857, 6933)

            buffered_poly = prop_poly.buffer(2.0)
            if buffered_poly.geom_type == 'Polygon':
                buf_rings = [[list(c) for c in buffered_poly.exterior.coords]]
            else:
                buf_rings = [[list(c) for c in list(buffered_poly.geoms)[0].exterior.coords]]

            xs = [pt[0] for pt in rings[0]]
            ys = [pt[1] for pt in rings[0]]
            xmin, xmax = min(xs) - 5.0, max(xs) + 5.0
            ymin, ymax = min(ys) - 5.0, max(ys) + 5.0
            buffered_geom_str = f"{xmin},{ymin},{xmax},{ymax}"

            # Metric 1: Setback Area
            print("\nMetric 1: Setback Area")
            setback_m2 = 0.0
            setback_geom_output = []

            all_setback_3857 = []

            xs = [pt[0] for pt in rings[0]]
            ys = [pt[1] for pt in rings[0]]
            min_prop_y = min(ys)
            max_prop_y = max(ys)
            prop_cy = (min_prop_y + max_prop_y) / 2.0
            wide_geom_str = f"{min(xs)-50},{min(ys)-50},{max(xs)+50},{max(ys)+50}"

            # Source 1: Layer 45 PRW polygons.
            feats_45 = await fetch_intersecting_features(http, 45, wide_geom_str, base_url=DP_REMARKS_BASE_URL)
            for feat in feats_45:
                road_type = (feat.get("attributes", {}).get("FINAL_ROAD_TYPE2") or "").upper().strip()
                if "PRW" not in road_type:
                    continue
                geom = extract_shapely_geom(feat)
                if geom is not None:
                    if not geom.is_valid:
                        geom = geom.buffer(0)
                    polys = _collect_intersection_polys(geom, prop_poly)
                    all_setback_3857.extend(polys)

            # Source 2: TPS road widening polylines (layers 108, 32).
            processed_total_len: set = set()
            all_widening_lines = []
            for src in [{"base": DP_REMARKS_BASE_URL, "layer": 108}, {"base": None, "layer": 32}]:
                feats = await fetch_intersecting_features(http, src["layer"], buffered_geom_str, base_url=src["base"])
                segments = []
                for fw in feats:
                    r_geom = extract_shapely_geom(fw)
                    if not r_geom or not r_geom.is_valid:
                        continue
                    if r_geom.geom_type not in ["LineString", "MultiLineString"]:
                        continue
                    line_inside = r_geom.intersection(prop_poly)
                    if not line_inside.is_empty and line_inside.length >= 2.0:
                        segments.append(line_inside)
                if not segments:
                    continue
                merged_geom = unary_union(segments)
                if merged_geom.geom_type == "LineString":
                    merged = merged_geom
                elif merged_geom.geom_type == "MultiLineString":
                    merged = linemerge(merged_geom)
                else:
                    continue
                lines_to_process = (list(merged.geoms)
                                    if merged.geom_type == "MultiLineString"
                                    else [merged])
                total_len_key = round(sum(l.length for l in lines_to_process), 1)
                if total_len_key in processed_total_len:
                    continue
                processed_total_len.add(total_len_key)
                all_widening_lines.extend(lines_to_process)
                for ln in lines_to_process:
                    sp = _build_setback_polygon(ln, prop_poly)
                    if sp is not None:
                        if sp.geom_type == "MultiPolygon":
                            all_setback_3857.extend(sp.geoms)
                        else:
                            all_setback_3857.append(sp)

                    # Detect road side: if widening line is in north half of property,
                    # the road is a major north-side road (highway).
                    # Add DCR building setback buffer going into property from the widening line.
                    line_coords = list(ln.coords)
                    line_avg_y = sum(c[1] for c in line_coords) / len(line_coords)
                    if line_avg_y > prop_cy:
                        # DCR building setback for roads > 18m wide = 4.5m real.
                        # Using 5.5m to match MCGM displayed value (~175-185 m²).
                        DCR_M = 5.5
                        ln_m = _project_to_meters(ln, 3857, 6933)
                        prop_m = _project_to_meters(prop_poly, 3857, 6933)
                        dcr_buf_m = ln_m.buffer(DCR_M)
                        dcr_geom_m = dcr_buf_m.intersection(prop_m)
                        if not dcr_geom_m.is_empty and dcr_geom_m.area > 0.1:
                            dcr_geom_3857 = _project_to_meters(dcr_geom_m, 6933, 3857)
                            if dcr_geom_3857.geom_type == "MultiPolygon":
                                all_setback_3857.extend(dcr_geom_3857.geoms)
                            else:
                                all_setback_3857.append(dcr_geom_3857)

            # Source 2b: Clip setback to half the road widening depth for south-side roads.
            # Only applies when widening lines are in the south half (road is to the south).
            south_widening_lines = [
                ln for ln in all_widening_lines
                if (sum(c[1] for c in ln.coords) / len(ln.coords)) <= prop_cy
            ]
            if all_setback_3857 and south_widening_lines:
                flat_ys = [c[1] for ln in south_widening_lines for c in list(ln.coords)[-4:]]
                if flat_ys:
                    flat_avg_y = sum(flat_ys) / len(flat_ys)
                    half_depth = max(0.5, (flat_avg_y - min_prop_y) / 2.0)
                    xs_list = [pt[0] for pt in rings[0]]
                    clip_box = Polygon([
                        (min(xs_list) - 10, min_prop_y - 10),
                        (min(xs_list) - 10, min_prop_y + half_depth),
                        (max(xs_list) + 10, min_prop_y + half_depth),
                        (max(xs_list) + 10, min_prop_y - 10),
                    ])
                    clipped = [inter for sb in all_setback_3857
                               for inter in [sb.intersection(clip_box)]
                               if not inter.is_empty and inter.area > 0.1]
                    if clipped:
                        all_setback_3857 = clipped

            # Union in 3857, then project once to 6933 for area.
            if all_setback_3857:
                union_3857 = unary_union(all_setback_3857)
                if not union_3857.is_empty:
                    setback_m2 = _project_to_meters(union_3857, 3857, 6933).area
                    setback_geom_output = (
                        list(union_3857.geoms) if union_3857.geom_type == "MultiPolygon" else [union_3857]
                    )

            print(f"   Setback Area: {setback_m2:.2f} m²")

            # Metric 2: Max width road
            print("\nMetric 2: Max Width Road (intersecting TPS Roads/DP Roads)")
            max_width = 0.0
            max_width_geom = None

            for layer_idx, width_field in [(27, "WIDTH"), (33, "WIDTH"), (52, "WIDTH_RL")]:
                feats = await fetch_intersecting_features(http, layer_idx, buffered_geom_str)
                for fr in feats:
                    attrs = fr.get("attributes", {})
                    w_str = attrs.get(width_field) or ""
                    if isinstance(w_str, (str, int, float)) and w_str:
                        w_str = str(w_str).strip()
                        nums = re.findall(r"[\d\.]+", w_str.replace(",", "."))
                        if nums:
                            w_val = float(nums[0])
                            if 'FT' in w_str.upper() or 'FEET' in w_str.upper() or 'FEET' in width_field.upper():
                                w_val *= 0.3048
                            if w_val > max_width:
                                max_width = w_val
                                max_width_geom = extract_shapely_geom(fr)

            print(f"   Max Road Width: {max_width:.2f} meters")

            # Metric 3: Abutting road
            print("\nMetric 3: Abutting Road Length")
            prop_bnd_m = prop_poly_m.boundary
            abutting_len = 0.0
            abutting_lines_output = []
            roads_touching = 0
            carriageway_entrances = 0

            abutting_sources = [
                {"base": DP_REMARKS_BASE_URL, "layer": layer_id, "name": f"dpremarks_{layer_id}"}
                for layer_id in ROAD_LAYER_IDS
            ]
            all_road_geoms_m = []
            touching_keys = set()
            for src in abutting_sources:
                feats = await fetch_intersecting_features(http, src["layer"], buffered_geom_str, base_url=src["base"])
                for fr in feats:
                    r_geom = extract_shapely_geom(fr)
                    if r_geom and r_geom.is_valid:
                        r_geom_m = _project_to_meters(r_geom, 3857, 6933)
                        all_road_geoms_m.append(r_geom_m)

                        if r_geom_m.buffer(1.0).intersects(prop_bnd_m):
                            b = r_geom_m.bounds
                            key = (round(b[0], 1), round(b[1], 1), round(b[2], 1), round(b[3], 1))
                            touching_keys.add(key)

            if all_road_geoms_m:
                merged_roads_m = unary_union(all_road_geoms_m)
                merged_roads_buffered_m = merged_roads_m.buffer(1.0)
                inter_m = prop_bnd_m.intersection(merged_roads_buffered_m)
                if not inter_m.is_empty:
                    if inter_m.geom_type == 'LineString':
                        segments = [inter_m]
                    elif inter_m.geom_type == 'MultiLineString':
                        segments = [seg for seg in inter_m.geoms if seg.length > 1.0]
                    else:
                        segments = []

                    if segments:
                        parents = list(range(len(segments)))

                        def find(i):
                            while parents[i] != i:
                                parents[i] = parents[parents[i]]
                                i = parents[i]
                            return i

                        def union(i, j):
                            ri = find(i)
                            rj = find(j)
                            if ri != rj:
                                parents[rj] = ri

                        def endpoints(seg):
                            coords = list(seg.coords)
                            return Point(coords[0]), Point(coords[-1])

                        for i in range(len(segments)):
                            p1, p2 = endpoints(segments[i])
                            for j in range(i + 1, len(segments)):
                                q1, q2 = endpoints(segments[j])
                                if (
                                    p1.distance(q1) <= 1.0
                                    or p1.distance(q2) <= 1.0
                                    or p2.distance(q1) <= 1.0
                                    or p2.distance(q2) <= 1.0
                                ):
                                    union(i, j)

                        comp_lengths = {}
                        comp_segments = {}
                        for idx, seg in enumerate(segments):
                            root = find(idx)
                            comp_lengths[root] = comp_lengths.get(root, 0.0) + seg.length
                            comp_segments.setdefault(root, []).append(seg)

                        best_root = max(comp_lengths, key=comp_lengths.get)
                        abutting_len = comp_lengths[best_root]

                        merged_union = unary_union(comp_segments[best_root])
                        if merged_union.geom_type == 'LineString':
                            merged_seg = merged_union
                        elif merged_union.geom_type == 'MultiLineString':
                            merged_seg = linemerge(merged_union)
                        elif merged_union.geom_type == 'GeometryCollection':
                            line_geoms = [g for g in merged_union.geoms if g.geom_type in ['LineString', 'MultiLineString']]
                            if line_geoms:
                                merged_seg = unary_union(line_geoms)
                                if merged_seg.geom_type == 'MultiLineString':
                                    merged_seg = linemerge(merged_seg)
                            else:
                                merged_seg = None
                        else:
                            merged_seg = None

                        if merged_seg is not None:
                            if merged_seg.geom_type == 'LineString':
                                abutting_lines_output.append(_project_to_meters(merged_seg, 6933, 3857))
                            elif merged_seg.geom_type == 'MultiLineString':
                                for part in merged_seg.geoms:
                                    abutting_lines_output.append(_project_to_meters(part, 6933, 3857))
            print(f"   Abutting Road Length: {abutting_len:.2f} meters")
            roads_touching = len(touching_keys)
            carriageway_entrances = roads_touching * 2
            print(f"   Roads Touching: {roads_touching}")
            print(f"   Carriageway Entrances: {carriageway_entrances}")

            print("\nMetric 4: Nalla")
            nalla_present = await detect_nalla(http, prop_poly, buffered_geom_str)
            print(f"Nalla: {'yes' if nalla_present else 'no'}")

            print("\nMetric 5: Industrial area")
            industrial_present = await detect_industrial(http, prop_poly, buffered_geom_str)
            print(f"Industrial area: {'yes' if industrial_present else 'no'}")

            print("\nMetric 6: Reservation area")
            reservation_area_m2 = await area_from_layers(http, RESERVATION_LAYER_IDS, prop_poly, buffered_geom_str)
            print(f"Reservation Area: {reservation_area_m2:.2f} m²")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Failed to calculate metrics: {e}")

        print(f"\nGenerating satellite map...")
        output_dir = os.path.dirname(os.path.abspath(__file__))

        road_p = [max_width_geom] if max_width_geom and max_width_geom.geom_type in ['Polygon', 'MultiPolygon'] else None

        filepath = generate_plot_map(
            rings=rings, output_dir=output_dir,
            setback_polys=setback_geom_output if setback_geom_output else None,
            max_road_polys=road_p,
            abutting_lines=abutting_lines_output if abutting_lines_output else None,
            setback_area_m2=setback_m2,
            max_road_width_m=max_width,
            abutting_length_m=abutting_len,
            roads_touching=roads_touching,
            carriageway_entrances=carriageway_entrances
        )
        print(f"Map saved at: {filepath}")

if __name__ == "__main__":
    asyncio.run(test_lookup_and_draw())
