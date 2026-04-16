import asyncio
import os
import sys
from pathlib import Path

# Setup paths
root = Path(__file__).parent.parent.parent.absolute()
sys.path.append(str(root))

# The report_generator service expects its own root in path to resolve "services.xxx"
report_gen_root = root / "services" / "report_generator"
sys.path.insert(0, str(report_gen_root))

from services.template_service import template_service
from core.config import settings, resolve_scheme_key

async def verify_template_loading():
    print("=== VERIFYING TEMPLATE LOADING FOR 33(20)(B) ===")
    
    scheme = "33(20)(B)"
    rd_type = "CLUBBING"
    
    # 1. Verify Scheme Resolution
    resolved_key = resolve_scheme_key(scheme, rd_type)
    print(f"1. Requested: {scheme} | Resolved Key: {resolved_key}")
    
    # 2. Verify Mapping
    template_file = settings.SCHEME_TEMPLATE_MAP.get(resolved_key)
    print(f"2. Mapped Template File: {template_file}")
    
    template_path = settings.TEMPLATES_DIR / template_file
    print(f"3. Full Template Path: {template_path}")
    
    if template_path.exists():
        print("   SUCCESS: Template file exists on disk.")
    else:
        print("   FAILED: Template file NOT found.")
        return

    # 3. Test simple generation (mock data)
    print("4. Testing report generation (internal call)...")
    try:
        all_data = {
            "society_name": "Verification Test",
            "plot_area_sqm": 1500,
            "road_width_m": 18.3,
            "num_flats": 20,
            "financial": {"sale_rate_sqft": 65000},
            "ready_reckoner": {"rr_open_land_sqm": 210000}
        }
        
        # We don't need a real output path for bytes test
        excel_bytes, saved_path = template_service.generate_full_report(
            scheme=scheme,
            all_data=all_data,
            redevelopment_type=rd_type
        )
        
        print(f"   SUCCESS: Generated {len(excel_bytes)} bytes.")
        print(f"   Saved to: {saved_path}")
        
    except Exception as e:
        print(f"   FAILED: Generation error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_template_loading())
