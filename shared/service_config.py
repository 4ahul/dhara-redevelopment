"""
Shared Service Configuration
Single source of truth for all services and their expected data structures.
"""

from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class ServiceConfig:
    name: str
    port: int
    endpoint: str
    required_fields: List[str]
    optional_fields: List[str] = field(default_factory=list)


SERVICES: Dict[str, ServiceConfig] = {
    "site_analysis": ServiceConfig(
        name="Site Analysis",
        port=8001,
        endpoint="/analyse",
        required_fields=["address"],
        optional_fields=["ward", "plot_no"],
    ),
    "height_service": ServiceConfig(
        name="Height Service",
        port=8002,
        endpoint="/height",
        required_fields=["lat", "lng"],
        optional_fields=["site_elevation"],
    ),
    "ready_reckoner": ServiceConfig(
        name="Ready Reckoner",
        port=8003,
        endpoint="/rates",
        required_fields=["ward"],
        optional_fields=["year"],
    ),
    "premium_checker": ServiceConfig(
        name="Premium Checker",
        port=8004,
        endpoint="/calculate",
        required_fields=["plot_area_sqm", "permissible_bua_sqft"],
        optional_fields=[
            "commercial_bua_sqft",
            "residential_bua_sqft",
            "rr_open_land_sqm",
            "scheme",
        ],
    ),
    "zone_regulations": ServiceConfig(
        name="Zone Regulations",
        port=8007,
        endpoint="/analyze",
        required_fields=["lat", "lng"],
        optional_fields=["address"],
    ),
    "dp_report": ServiceConfig(
        name="DP Report",
        port=8008,
        endpoint="/report",
        required_fields=["lat", "lng"],
        optional_fields=["ward", "address"],
    ),
    "pr_card_scraper": ServiceConfig(
        name="PR Card Scraper",
        port=8006,
        endpoint="/scrape",
        required_fields=["district", "taluka", "village", "survey_no"],
        optional_fields=["sheet_number", "plot_number"],
    ),
    "report_generator": ServiceConfig(
        name="Report Generator",
        port=8005,
        endpoint="/generate",
        required_fields=["society_name"],
        optional_fields=[
            "ref_no",
            "property_desc",
            "location",
            "ward",
            "zone",
            "plot_area_sqm",
            "road_width_m",
            "num_flats",
            "num_commercial",
            "commercial_units",
            "residential_units",
            "fsi",
            "bua",
            "financial",
            "additional_entitlement",
            "site_analysis",
            "height",
            "ready_reckoner",
            "premium",
            "zone_regulations",
            "dp_report",
            "llm_analysis",
        ],
    ),
}


SERVICE_OUTPUT_SCHEMA: Dict[str, Dict[str, Any]] = {
    "site_analysis": {
        "lat": "float",
        "lng": "float",
        "formatted_address": "str",
        "area_type": "str",
        "nearby_landmarks": "list[str]",
        "place_id": "str",
        "zone_inference": "str",
        "maps_url": "str",
    },
    "height_service": {
        "lat": "float",
        "lng": "float",
        "max_height_m": "float",
        "max_floors": "int",
        "restriction_reason": "str",
        "nocas_reference": "str",
        "aai_zone": "str",
        "rl_datum_m": "float",
    },
    "ready_reckoner": {
        "ward": "str",
        "ward_name": "str",
        "zone": "str",
        "rr_open_land_sqm": "float",
        "rr_residential_sqm": "float",
        "rr_commercial_ground_sqm": "float",
        "rr_commercial_upper_sqm": "float",
        "rr_construction_cost_sqm": "float",
        "year": "int",
        "source": "str",
        "additional_fsi_premium_rate": "float",
        "fungible_residential_rate": "float",
        "fungible_commercial_rate": "float",
        "slum_tdr_rate": "float",
        "general_tdr_rate": "float",
        "staircase_premium_rate": "float",
    },
    "premium_checker": {
        "scheme": "str",
        "line_items": "list[dict]",
        "total_fsi_tdr_premiums": "float",
        "total_mcgm_charges": "float",
        "grand_total": "float",
        "grand_total_crore": "float",
    },
    "zone_regulations": {
        "crz_zone": "str",
        "crz_status": "str",
        "crz_noc_required": "bool",
        "cod_area": "bool",
        "dcpr_zone": "str",
        "dcpr_regulations": "list[str]",
        "special_designation": "str",
        "max_fsi": "float",
        "setback_requirements": "str",
        "parking_requirements": "str",
        "remarks": "str",
    },
    "dp_report": {
        "ward": "str",
        "taluka": "str",
        "zone": "str",
        "sub_zone": "str",
        "dp_year": "int",
        "total_area_sqm": "float",
        "road_width_proposed": "float",
        "reservations": "list[dict]",
        "plots": "list[dict]",
        "building_permission_zone": "str",
        "allowed_uses": "list[str]",
        "restrictions": "list[str]",
        "remarks": "str",
    },
}


WORKFLOW_STEPS = [
    {
        "step": 1,
        "service": "site_analysis",
        "depends_on": [],
        "provides": ["lat", "lng", "ward", "area_type", "zone_inference"],
    },
    {
        "step": 2,
        "service": "height_service",
        "depends_on": [1],
        "provides": ["max_height_m", "max_floors", "aai_zone"],
    },
    {
        "step": 3,
        "service": "zone_regulations",
        "depends_on": [1],
        "provides": ["crz_zone", "dcpr_zone", "regulations"],
    },
    {
        "step": 4,
        "service": "dp_report",
        "depends_on": [1, 2],
        "provides": ["reservations", "allowed_uses", "restrictions"],
    },
    {
        "step": 5,
        "service": "ready_reckoner",
        "depends_on": [1],
        "provides": ["rr_rates", "premium_rates"],
    },
    {
        "step": 6,
        "service": "premium_checker",
        "depends_on": [5],
        "provides": ["total_charges", "breakdown"],
    },
    {
        "step": 7,
        "service": "report_generator",
        "depends_on": [1, 2, 3, 4, 5, 6],
        "provides": ["excel_report"],
    },
]


def get_service_url(service_name: str, internal: bool = True) -> str:
    """Get service URL."""
    if internal:
        return f"http://{service_name.replace('_', '_')}:{SERVICES[service_name].port}"
    return f"http://localhost:{SERVICES[service_name].port}"


def get_workflow_dependencies(service_name: str) -> List[str]:
    """Get all services this service depends on."""
    for step in WORKFLOW_STEPS:
        if step["service"] == service_name:
            deps = []
            for d in step["depends_on"]:
                for s in WORKFLOW_STEPS:
                    if s["step"] == d:
                        deps.append(s["service"])
            return deps
    return []
