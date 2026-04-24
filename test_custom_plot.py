"""
MCGM Property Lookup — Mirroring the official MCGM search portal
Two search modes exactly like the MCGM DP Sheet search:

  Mode "CTS"  →  Ward + Village + CTS Number
  Mode "FP"   →  Ward + TPS Scheme + FP Number
"""
import os
import asyncio
import json
import httpx
import importlib.util

# Load visualization directly
spec = importlib.util.spec_from_file_location(
    "visualization",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "services/mcgm_property_lookup/services/visualization.py")
)
vis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vis)
generate_plot_map = vis.generate_plot_map

# Load geometry for area
spec2 = importlib.util.spec_from_file_location(
    "geometry",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "services/mcgm_property_lookup/services/geometry.py")
)
geo = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(geo)

# ==============================================================================
# 🎯 Search Parameters
# ==============================================================================
MODE = "CTS"   # "CTS" or "FP"

WARD      = "H/W"
VILLAGE   = "BANDRA-F"
CTS_NO    = "1052"

TPS_NAME  = ""
FP_NO     = ""
# ==============================================================================

TPS_FP_LAYER_URL = "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3"

def build_where_clause() -> str:
    if MODE == "CTS":
        return f"WARD='{WARD}' AND UPPER(VILLAGE_NAME) LIKE UPPER('%{VILLAGE}%') AND CTS_CS_NO='{CTS_NO}'"
    return f"WARD='{WARD}' AND TPS_NAME='{TPS_NAME}' AND FP_NO='{FP_NO}'"

async def test_lookup_and_draw():
    where = build_where_clause()
    print(f"Search Mode : {MODE}")
    print(f"WHERE clause: {where}\n")

    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{TPS_FP_LAYER_URL}/query", params={
            "f": "json", "where": where, "outFields": "*", "returnGeometry": "true", "outSR": "102100",
        }, timeout=30.0)
        data = resp.json()

        features = data.get("features", [])
        if not features:
            print("❌ Property not found.")
            return

        feature = features[0]
        attrs = feature.get("attributes", {})

        print(f"✅ Property Found!")
        print(f"   Ward:       {attrs.get('WARD')}")
        print(f"   Village:    {attrs.get('VILLAGE_NAME')}")
        print(f"   TPS Name:   {attrs.get('TPS_NAME')}")
        print(f"   FP No:      {attrs.get('FP_NO')}")
        print(f"   CTS No:     {attrs.get('CTS_CS_NO')}")
        print(f"   Coordinates: {feature.get('geometry', {}).get('rings', [[]])[0][0]}")

        # Area calculation
        rings = feature.get("geometry", {}).get("rings", [])
        area = geo.polygon_area_sqm(rings)
        print(f"   Total Area: {area:.2f} m²")

        print(f"\nGenerating satellite map...")
        output_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = generate_plot_map(rings=rings, output_dir=output_dir)
        print(f"🚀 Map saved at: {filepath}")

if __name__ == "__main__":
    asyncio.run(test_lookup_and_draw())
