import asyncio, httpx, json

async def req():
    async with httpx.AsyncClient(verify=False) as http:
        where = "WARD='H/W' AND UPPER(VILLAGE_NAME) LIKE UPPER('%BANDRA-F%') AND CTS_CS_NO='1052'"
        r = await http.get('https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3/query', params={'f':'json','where':where,'outFields':'*','returnGeometry':'true','outSR':'102100'}, timeout=120)
        
        feature = r.json()['features'][0]
        geom = feature['geometry']
        geom_str = json.dumps(geom)
        print("geom_str length", len(geom_str))
        
        r3 = await http.get('https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/33/query', params={
            'f':'json','inSR':'102100','outSR':'102100','geometry':geom_str,'geometryType':'esriGeometryPolygon','spatialRel':'esriSpatialRelIntersects','outFields':'*','returnGeometry':'true'
        }, timeout=120)
        print('DP Roads (33)', len(r3.json().get('features', [])))
        
        r5 = await http.get('https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/40/query', params={
            'f':'json','inSR':'102100','outSR':'102100','geometry':geom_str,'geometryType':'esriGeometryPolygon','spatialRel':'esriSpatialRelIntersects','outFields':'*','returnGeometry':'true'
        }, timeout=120)
        print('Road Widening (40)', len(r5.json().get('features', [])))

if __name__=='__main__':
    asyncio.run(req())