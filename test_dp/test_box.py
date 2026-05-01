import asyncio
import json
import httpx

async def main():
    where = "WARD='K/W' AND UPPER(TPS_NAME) LIKE UPPER('%VILE PARLE No%VI%') AND FP_NO='50'"
    
    url = "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3/query"
    async with httpx.AsyncClient(verify=False) as http:
        resp = await http.get(url, params={
            "f": "json", "where": where, "outFields": "*", "returnGeometry": "true", "outSR": "102100"
        })
        data = resp.json()
        feature = data.get("features", [])[0]
        rings = feature["geometry"]["rings"]
        
        # Get bounding box
        xs = [pt[0] for pt in rings[0]]
        ys = [pt[1] for pt in rings[0]]
        xmin, xmax = min(xs) - 20, max(xs) + 20
        ymin, ymax = min(ys) - 20, max(ys) + 20
        
        env_str = f"{xmin},{ymin},{xmax},{ymax}"
        
        print("Checking bounding box for Layers...")
        for layer in [40, 32]:
            r = await http.get(f"https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/{layer}/query", params={
                "f": "json", "geometry": env_str, "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true",
                "inSR": "102100", "outSR": "102100"
            })
            feats = r.json().get("features", [])
            for f in feats: 
                 print(f"L{layer} Geom: {f.get('geometry')}")

if __name__ == "__main__":
    asyncio.run(main())
