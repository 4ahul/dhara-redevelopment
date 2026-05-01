import asyncio, httpx, json

async def req():
    async with httpx.AsyncClient(verify=False) as http:
        where = "WARD='K/W' AND UPPER(TPS_NAME) LIKE UPPER('%VILE PARLE No.VI%') AND FP_NO='50'"
        r = await http.get('https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3/query', params={'f':'json','where':where,'outFields':'*','returnGeometry':'true'}, timeout=120)
        
        js = r.json()
        features = js.get('features', [])
        if not features:
            print('Not found')
            return
            
        geom = features[0]['geometry']
        geom.update({'spatialReference': js.get('spatialReference', {'wkid': 102100})})
        geom_str = json.dumps(geom)
        print("Found geom for K/W FP 50")
        
        for layer in [25, 32, 33, 40, 68, 52]:
            r3 = await http.get(f'https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/{layer}/query', params={
                'f':'json',
                'geometry':geom_str,
                'geometryType':'esriGeometryPolygon',
                'spatialRel':'esriSpatialRelIntersects',
                'inSR': json.dumps(geom['spatialReference']), 
                'outFields':'*',
                'returnGeometry':'true'
            }, timeout=120)
            
            features = r3.json().get('features', [])
            geom_type = r3.json().get('geometryType', 'unknown')
            print(f'Layer {layer} ({geom_type}) features:', len(features))
            if len(features) > 0:
                print(f'Layer {layer} attributes:', features[0].get('attributes'))

if __name__ == '__main__':
    asyncio.run(req())