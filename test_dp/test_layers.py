import httpx
import urllib3
urllib3.disable_warnings()

def get_layers():
    r = httpx.get('https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer?f=json', verify=False)
    layers = r.json().get('layers', [])
    for l in layers:
        print(f"{l['id']}: {l['name']}")

get_layers()
