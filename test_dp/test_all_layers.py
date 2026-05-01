import asyncio
import httpx
import sys

async def main():
    prop = "WARD='K/W' AND UPPER(TPS_NAME) LIKE UPPER('%VILE PARLE No.VI%') AND FP_NO='18'"
    async with httpx.AsyncClient(verify=False) as http:
        url = "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3/query"
        r = await http.get(url, params={"f":"json", "where": prop, "outFields":"*", "returnGeometry":"true", "outSR": "3857"})
        data = r.json()
        if "features" not in data or not data["features"]:
            print("Property not found")
            return
        feat = data["features"][0]
        geom = feat["geometry"]
        xs = [pt[0] for pt in geom["rings"][0]]
        ys = [pt[1] for pt in geom["rings"][0]]
        b = f"{min(xs)-1},{min(ys)-1},{max(xs)+1},{max(ys)+1}"

        for i in [25, 27, 32, 33, 40, 52]:
            url2 = f"https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/{i}/query"
            r2 = await http.get(url2, params={
                "f":"json", "geometry": b, "geometryType": "esriGeometryEnvelope", 
                "spatialRel": "esriSpatialRelIntersects", "outFields": "*", 
                "returnGeometry": "true", "outSR": "3857"
            })
            d2 = r2.json()
            if "features" in d2 and d2["features"]:
                print(f"Layer {i}: {len(d2['features'])} features. Type: {list(d2['features'][0]['geometry'].keys())[0] if 'geometry' in d2['features'][0] else None}")
                for f in d2['features']:
                    attr = f.get('attributes', {})
                    obj_id = attr.get('OBJECTID', '?')
                    w = attr.get('WIDTH_RL', attr.get('WIDTH', attr.get('width', '')))
                    print(f"  - ObjID: {obj_id}, Width: {w}")

if __name__ == "__main__":
    asyncio.run(main())
