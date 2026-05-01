import asyncio
import httpx
import json
import geopandas as gpd
from shapely.geometry import Polygon, LineString, MultiLineString
from shapely.ops import split, snap
import urllib3
urllib3.disable_warnings()

async def main():
    where = "WARD='K/W' AND UPPER(TPS_NAME) LIKE UPPER('%VILE PARLE No.VI%') AND FP_NO='50'"
    async with httpx.AsyncClient(verify=False) as http:
        # Get Property
        r = await http.get("https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3/query", params={
            "f": "json", "where": where, "outFields": "*", "returnGeometry": "true", "outSR": "102100"
        })
        prop_feat = r.json().get("features", [])[0]
        prop_poly = Polygon(prop_feat["geometry"]["rings"][0])
        print(f"Property Area (approx mapped): {prop_poly.area}")

        # Bounding box
        xs = [pt[0] for pt in prop_feat["geometry"]["rings"][0]]
        ys = [pt[1] for pt in prop_feat["geometry"]["rings"][0]]
        xmin, xmax = min(xs) - 10, max(xs) + 10
        ymin, ymax = min(ys) - 10, max(ys) + 10
        geom_str = f"{xmin},{ymin},{xmax},{ymax}"

        # Fetch varying road line layers
        for layer in [32, 40, 52, 68]:
            r2 = await http.get(f"https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/{layer}/query", params={
                "f": "json", "geometry": geom_str, "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true",
                "inSR": "102100", "outSR": "102100"
            })
            feats = r2.json().get("features", [])
            for i, f in enumerate(feats):
                geom = f.get("geometry", {})
                
                # Check for line paths
                if "paths" in geom:
                    for path in geom["paths"]:
                        line = LineString(path)
                        inter = prop_poly.intersection(line)
                        print(f"Layer {layer} Line {i}: intersects property? {not inter.is_empty}, Intersection type: {inter.geom_type}")
                        if not inter.is_empty:
                            try:
                                snap_line = snap(line, prop_poly.boundary, 1.0)
                                parts = list(split(prop_poly, snap_line).geoms)
                                print(f"  Split parts: {len(parts)}")
                                if len(parts) == 1:
                                    bnd_inter = prop_poly.boundary.intersection(snap_line)
                                    print(f"  Boundary intersections with snapping: {bnd_inter.geom_type} - {list(bnd_inter.geoms) if hasattr(bnd_inter, 'geoms') else bnd_inter}")
                            except Exception as e:
                                print(f"  Split failed: {e}")
                
                # Check for polygon rings
                elif "rings" in geom:
                     for ring in geom["rings"]:
                        poly = Polygon(ring)
                        inter = prop_poly.intersection(poly)
                        print(f"Layer {layer} Polygon {i}: intersects property? {not inter.is_empty}, Intersection area: {inter.area}")


if __name__ == '__main__':
    asyncio.run(main())
