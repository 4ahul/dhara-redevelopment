import asyncio
import json
import httpx

async def main():
    geom_str = '{"rings": [[[8108873.328399999, 2167452.9231999964], [8108872.2478, 2167456.9698], [8108872.248300001, 2167466.1953000017], [8108873.743199997, 2167472.062099997], [8108881.0827, 2167490.871100001], [8108902.946999997, 2167484.580199998], [8108892.650899999, 2167453.7667999975], [8108873.328399999, 2167452.9231999964]]], "spatialReference": {"wkid": 102100}}'
    
    url = "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/{}/query"
    
    async with httpx.AsyncClient() as http:
        pass

        for layer in [30, 31, 68, 53, 54, 26, 28, 124, 43]: # Test remaining
            resp = await http.get(url.format(layer), params={
                "f": "json", "geometry": geom_str, "geometryType": "esriGeometryPolygon",
                "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true",
                "inSR": "102100", "outSR": "102100"
            })
            feats = resp.json().get("features", [])
            print(f"Layer {layer} Road Width Features:", len(feats))
            if feats:
                for f in feats:
                    print("Attrs:", f.get("attributes", {}))


if __name__ == "__main__":
    asyncio.run(main()) 
