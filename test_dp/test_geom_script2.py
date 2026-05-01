import asyncio, httpx, json

async def req():
    async with httpx.AsyncClient(verify=False) as http:
        where = "WARD='H/W' AND UPPER(VILLAGE_NAME) LIKE UPPER('%BANDRA-F%') AND CTS_CS_NO='1052'"
        r = await http.get('https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3/query', params={'f':'json','where':where,'outFields':'*','returnGeometry':'true'}, timeout=120)
        geom = r.json()['features'][0]['geometry']
        geom.update({"spatialReference": r.json()['spatialReference']})
        geom_str = json.dumps(geom)
        
        for layer in [25, 33, 40, 68, 52]:
            r3 = await http.get(f'https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/{layer}/query', params={
                'f':'json','geometry':geom_str,'geometryType':'esriGeometryPolygon','spatialRel':'esriSpatialRelIntersects','inSR': json.dumps(geom['spatialReference']), 'outFields':'*','returnGeometry':'true'
            }, timeout=120)
            features = r3.json().get('features', [])
            print(f'Layer {layer} features:', len(features))
            if len(features) > 0:
                print(f'Layer {layer} first feature keys:', features[0].keys())
                if 'attributes' in features[0]:
                    print(f'Layer {layer} attributes:', features[0]['attributes'])

if __name__=='__main__':
    asyncio.run(req())