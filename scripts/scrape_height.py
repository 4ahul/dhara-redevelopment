import asyncio
import csv
import sys
import os

service_dir = (
    r"C:\Users\Admin\Documents\Projects\redevelopment-ai\services\height_service"
)
sys.path.insert(0, service_dir)
os.chdir(service_dir)

from services.height_service import height_service

test_coords = [
    (19.016328299999998, 72.8291129),
    (19.0595596, 72.8295287),
    (18.998640599999998, 72.8173599),
    (19.1178548, 72.8631304),
    (19.0177989, 72.84781199999999),
]

address_names = [
    "Prabhadevi, Mumbai, India",
    "Bandra West, Mumbai, India",
    "Worli, Mumbai, India",
    "Andheri East, Mumbai, India",
    "Dadar, Mumbai, India",
]


async def main():
    results = []
    for i, (lat, lng) in enumerate(test_coords):
        print(f"Processing: {address_names[i]} ({lat}, {lng})")
        result = await height_service.get_height(lat, lng)
        results.append(
            {
                "address": address_names[i],
                "lat": lat,
                "lng": lng,
                "max_height_m": result.get("max_height_m"),
                "max_floors": result.get("max_floors"),
                "restriction_reason": result.get("restriction_reason"),
                "aai_zone": result.get("aai_zone"),
                "nocas_reference": result.get("nocas_reference"),
            }
        )
        print(
            f"  -> Max Height: {result.get('max_height_m')}m, Floors: {result.get('max_floors')}"
        )

    output_file = "property_heights.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "address",
                "lat",
                "lng",
                "max_height_m",
                "max_floors",
                "restriction_reason",
                "aai_zone",
                "nocas_reference",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
