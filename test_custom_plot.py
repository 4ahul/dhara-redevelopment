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

# Load visualization directly to avoid broken __init__.py imports
spec = importlib.util.spec_from_file_location(
    "visualization",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "services/mcgm_property_lookup/services/visualization.py")
)
vis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vis)
generate_plot_map = vis.generate_plot_map

# ==============================================================================
# 🎯 STEP 1: Choose your search mode
#   "CTS"  →  search by Ward + Village + CTS Number
#   "FP"   →  search by Ward + TPS Scheme + FP Number
# ==============================================================================

MODE = "CTS"   # Change to "CTS" or "FP"

# ==============================================================================
# 🎯 STEP 2: Fill in the fields for your chosen mode
#
# If MODE = "CTS", fill these:
WARD    = "H/W"
VILLAGE = "BANDRA-F"
CTS_NO  = "1052"

# If MODE = "FP", fill these:
# WARD     = "K/W"    (same field, already filled above)
TPS_NAME  = "TPS VILE PARLE No.VI"
FP_NO     = ""
# ==============================================================================

TPS_FP_LAYER_URL = "https://agsmaps.mcgm.gov.in/server/rest/services/Development_Department/MapServer/3"


def build_where_clause() -> str:
    if MODE == "CTS":
        village_safe = VILLAGE.replace("'", "''")
        ward_safe = WARD.replace("'", "''")
        return (
            f"WARD='{ward_safe}'"
            f" AND UPPER(VILLAGE_NAME) LIKE UPPER('%{village_safe}%')"
            f" AND CTS_CS_NO='{CTS_NO.strip()}'"
        )
    elif MODE == "FP":
        tps_safe = TPS_NAME.replace("'", "''")
        ward_safe = WARD.replace("'", "''")
        return (
            f"WARD='{ward_safe}'"
            f" AND TPS_NAME='{tps_safe}'"
            f" AND FP_NO='{FP_NO.strip()}'"
        )
    else:
        raise ValueError(f"Invalid MODE '{MODE}'. Choose 'CTS' or 'FP'.")


async def test_lookup_and_draw():
    where = build_where_clause()
    print(f"Search Mode : {MODE}")
    print(f"WHERE clause: {where}\n")

    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{TPS_FP_LAYER_URL}/query", params={
            "f": "json",
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "102100",
        }, timeout=30.0)
        data = resp.json()

        if "error" in data:
            print(f"❌ API Error: {data['error']}")
            return

        features = data.get("features", [])
        print(f"Returned {len(features)} feature(s).")

        if not features:
            print("\n❌ Property not found. Please check your inputs.")
            return

        if len(features) > 1:
            print(f"\n⚠️  Multiple matches — showing all, mapping the first one:")
            for i, f in enumerate(features):
                a = f["attributes"]
                print(f"  [{i+1}] Ward: {a.get('WARD')} | TPS: {a.get('TPS_NAME')} | "
                      f"FP: {a.get('FP_NO')} | CTS: {a.get('CTS_CS_NO')} | Village: {a.get('VILLAGE_NAME')}")
            print()

        feature = features[0]
        attrs = feature.get("attributes", {})

        print(f"✅ Property Found!")
        print(f"   Ward:       {attrs.get('WARD')}")
        print(f"   Village:    {attrs.get('VILLAGE_NAME')}")
        print(f"   TPS Name:   {attrs.get('TPS_NAME')}")
        print(f"   FP No:      {attrs.get('FP_NO')}")
        print(f"   CTS No:     {attrs.get('CTS_CS_NO')}")
        print(f"   Area:       {attrs.get('SHAPE.AREA')} m²")

        rings = feature.get("geometry", {}).get("rings", [])
        if not rings:
            print("\n❌ Property found but geometry is empty.")
            return

        print(f"\nGenerating satellite map via Cartopy...")
        output_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            filepath = generate_plot_map(rings=rings, output_dir=output_dir)
            print(f"\n🚀 SUCCESS! Map saved at:\n   {filepath}")
        except Exception as e:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_lookup_and_draw())
