import asyncio
import csv
import sys
import os

service_dir = (
    r"C:\Users\Admin\Documents\Projects\redevelopment-ai\services\site_analysis"
)
sys.path.insert(0, service_dir)

os.chdir(service_dir)

from services import site_analysis_service

test_addresses = [
    "Prabhadevi, Mumbai, India",
    "Bandra West, Mumbai, India",
    "Worli, Mumbai, India",
    "Andheri East, Mumbai, India",
    "Dadar, Mumbai, India",
]


async def main():
    results = []
    for addr in test_addresses:
        print(f"Processing: {addr}")
        result = await site_analysis_service.analyse(address=addr)
        results.append(
            {
                "address": addr,
                "lat": result.get("lat"),
                "lng": result.get("lng"),
                "formatted_address": result.get("formatted_address"),
                "area_type": result.get("area_type"),
                "zone": result.get("zone_inference"),
                "maps_url": result.get("maps_url"),
            }
        )
        print(f"  -> Lat: {result.get('lat')}, Lng: {result.get('lng')}")

    # Save to CSV
    output_file = "property_coordinates.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "address",
                "lat",
                "lng",
                "formatted_address",
                "area_type",
                "zone",
                "maps_url",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
