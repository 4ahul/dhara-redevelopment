import httpx
import urllib3
urllib3.disable_warnings()

def check_layers():
    layers = [32, 33, 40, 52, 27, 25, 68, 53, 54]
    for l in layers:
        r = httpx.get(f'https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/{l}?f=json', verify=False)
        data = r.json()
        print(f"Layer {l}: {data.get('name')} | Type: {data.get('geometryType')} | Fields: {[f['name'] for f in data.get('fields', [])]}")

check_layers()
