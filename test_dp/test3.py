import asyncio, httpx, json
from shapely.geometry import shape, Polygon
import geopandas as gpd

async def req():
    async with httpx.AsyncClient(verify=False) as http:
        where = "WARD='K/W' AND UPPER(TPS_NAME) LIKE UPPER('%VILE PARLE No.VI%') AND FP_NO='50'"
        r = await http.get('https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3/query', params={'f':'json','where':where,'outFields':'*','returnGeometry':'true'}, timeout=120)
        
        js = r.json()
        feature = js['features'][0]
        prop_geom_esri = feature['geometry']
        
        # Manually construct geojson from esri geometry
        # ESRI polygon rings: [[[x,y], [x,y]]] -> GeoJSON coordinates: [[[x,y], [x,y]]]
        prop_polygon = Polygon(prop_geom_esri['rings'][0])
        
        # Calculate property area
        gdf_prop = gpd.GeoDataFrame(geometry=[prop_polygon], crs="EPSG:102100")
        gdf_prop_m = gdf_prop.to_crs(epsg=6933)
        prop_area = gdf_prop_m.area.iloc[0]
        print(f"Property Area: {prop_area:.2f} sqm")
        
        geom_str = json.dumps(prop_geom_esri)
        
        for layer, name in [(25, 'EXISTING ROAD'), (33, 'DP ROADS'), (27, 'TPS ROADS')]:
            r3 = await http.get(f'https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/{layer}/query', params={
                'f':'json', 'geometry':geom_str, 'geometryType':'esriGeometryPolygon', 'spatialRel':'esriSpatialRelIntersects', 'inSR': '102100', 'outFields':'*', 'returnGeometry':'true'
            }, timeout=120)
            
            features = r3.json().get('features', [])
            print(f"---\nLayer {layer} ({name}) - {len(features)} intersecting features")
            
            intersection_area = 0
            abutting_length = 0
            
            for f in features:
                if 'rings' in f['geometry']:
                    road_poly = Polygon(f['geometry']['rings'][0])
                    # Fix invalid geometries if any
                    if not road_poly.is_valid:
                        road_poly = road_poly.buffer(0)
                        
                    # Calculate Area
                    inter = prop_polygon.intersection(road_poly)
                    if not inter.is_empty:
                        gdf_inter = gpd.GeoDataFrame(geometry=[inter], crs="EPSG:102100").to_crs(epsg=6933)
                        area = gdf_inter.area.iloc[0]
                        intersection_area += area
                        
                        # Calculate abutting length
                        # The shared boundary length between the property outline and the road 
                        shared_boundary = prop_polygon.boundary.intersection(road_poly)
                        if not shared_boundary.is_empty:
                            gdf_bound = gpd.GeoDataFrame(geometry=[shared_boundary], crs="EPSG:102100").to_crs(epsg=6933)
                            length = gdf_bound.length.iloc[0]
                            abutting_length += length
                            
                    print(f"Road: {f['attributes'].get('NAME') or f['attributes'].get('ROADNAME', 'Unknown')}, Width attr: {f['attributes'].get('WIDTH')}")
            
            print(f"Total Intersection Area (Setback?): {intersection_area:.2f} sqm")
            print(f"Total Abutting Length: {abutting_length:.2f} m")

if __name__ == '__main__':
    asyncio.run(req())
