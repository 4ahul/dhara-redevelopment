"""
Dhara AI — Agent Tool Definitions
Schemas for all tools available to the LLM agent.
"""

TOOLS = [
    {
        "name": "analyse_site",
        "description": "Analyse a Mumbai plot's location using Google Maps. Returns lat/lng, area type, nearby landmarks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Full address of the plot",
                },
                "ward": {"type": "string", "description": "BMC ward e.g. 'G/S'"},
                "plot_no": {"type": "string", "description": "FP/CTS number"},
            },
            "required": ["address"],
        },
    },
    {
        "name": "get_max_height",
        "description": "Query NOCAS for maximum building height (AMSL and AGL) at given coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Latitude"},
                "lng": {"type": "number", "description": "Longitude"},
                "site_elevation": {
                    "type": "number",
                    "description": "Ground elevation in meters (optional, default 0)",
                },
            },
            "required": ["lat", "lng"],
        },
    },
    {
        "name": "calculate_premiums",
        "description": "Calculate all government premiums (FSI, TDR, fungible, MCGM charges) and property base value using IGR Ready Reckoner rates.",
        "input_schema": {
            "type": "object",
            "properties": {
                # Location — used to match the correct RR rate record
                "district": {
                    "type": "string",
                    "description": "District name. Default: 'mumbai'",
                },
                "taluka": {
                    "type": "string",
                    "description": "Taluka name. Default: 'mumbai-city'",
                },
                "locality": {
                    "type": "string",
                    "description": "Neighbourhood name e.g. 'prabhadevi', 'bandra', 'worli', 'bhuleshwar'",
                },
                "zone": {
                    "type": "string",
                    "description": "RR zone number e.g. '5', '6', '5/43'",
                },
                "sub_zone": {
                    "type": "string",
                    "description": "Sub-zone string if applicable. Leave '' if unknown.",
                },
                # Scheme & property type
                "scheme": {
                    "type": "string",
                    "description": "DCPR scheme e.g. '33(7)(B)', '33(20)(B)'. Default: '33(7)'",
                },
                "property_type": {
                    "type": "string",
                    "description": "'residential', 'commercial', or 'open_land'. Default: 'residential'",
                },
                # Area inputs
                "plot_area_sqm": {"type": "number", "description": "Plot area in sqm"},
                "property_area_sqm": {
                    "type": "number",
                    "description": "Existing built-up area in sqm",
                },
                "permissible_bua_sqft": {
                    "type": "number",
                    "description": "Total permissible BUA in sqft (plot_sqm × 10.764 × total_FSI)",
                },
                "residential_bua_sqft": {
                    "type": "number",
                    "description": "Residential component of BUA in sqft",
                },
                "commercial_bua_sqft": {
                    "type": "number",
                    "description": "Commercial component of BUA in sqft (0 if none)",
                },
                "fungible_residential_sqft": {
                    "type": "number",
                    "description": "Fungible BUA for residential (35% of residential BUA)",
                },
                # DCPR ratios (Mumbai defaults — only override if Step 5 provides different values)
                "premium_fsi_ratio": {
                    "type": "number",
                    "description": "Premium FSI ratio. Default: 0.50",
                },
                "amenities_premium_percentage": {"type": "number"},
                "depreciation_percentage": {"type": "number"},
            },
            "required": ["locality", "zone", "plot_area_sqm", "permissible_bua_sqft"],
        },
    },
    {
        "name": "generate_feasibility_report",
        "description": "Generate the final professional Excel feasibility report with all data. Uses templates based on scheme + redevelopment_type and applies all microservice data to yellow cells.",
        "input_schema": {
            "type": "object",
            "properties": {
                # Scheme selection - determines which template to use
                "scheme": {
                    "type": "string",
                    "description": "DCPR scheme. Valid values: '30(A)', '33(7)(A)', '33(7)(B)', '33(9)', '33(12)(B)', '33(12)(B)_ONLY', '33(19)', '33(20)(B)'. Use the scheme from user input if provided, otherwise determine from query_regulations.",
                },
                "redevelopment_type": {
                    "type": "string",
                    "enum": ["CLUBBING", "INSITU"],
                    "description": "Redevelopment approach: 'CLUBBING' (multiple societies combine, default) or 'INSITU' (on-site redevelopment). Use value from user input.",
                },
                # Cover sheet
                "society_name": {
                    "type": "string",
                    "description": "Housing society name",
                },
                "property_desc": {
                    "type": "string",
                    "description": "Short property description",
                },
                "location": {
                    "type": "string",
                    "description": "Full address / formatted address",
                },
                "ward": {"type": "string", "description": "BMC ward e.g. 'G/S'"},
                "zone": {
                    "type": "string",
                    "description": "DP zone code e.g. 'R1', 'C1'",
                },
                "plot_area_sqm": {
                    "type": "number",
                    "description": "Plot area in sqm (from Step 0 or user)",
                },
                "road_width_m": {
                    "type": "number",
                    "description": "Road width in metres (from Step 2)",
                },
                "num_flats": {
                    "type": "integer",
                    "description": "Number of existing residential units",
                },
                "num_commercial": {
                    "type": "integer",
                    "description": "Number of existing commercial units",
                },
                # Society existing carpet areas (map to Details!O53 and Details!Q53)
                "existing_commercial_carpet_sqft": {
                    "type": "number",
                    "description": "Existing commercial carpet area in sqft (from user input)",
                },
                "existing_residential_carpet_sqft": {
                    "type": "number",
                    "description": "Existing residential carpet area in sqft (from user input)",
                },
                "sale_rate_per_sqft": {
                    "type": "number",
                    "description": "Residential sale rate in ₹/sqft (maps to P&L!D28, fallback if not in financial dict)",
                },
                # Core data dicts — pass the full tool response dict for each
                "fsi": {
                    "type": "object",
                    "description": "FSI breakdown per scheme. Construct with keys: base_fsi, additional_fsi, tdr, fungible, total_fsi, total_with_fungible, scheme.",
                },
                "bua": {
                    "type": "object",
                    "description": "BUA breakdown: permissible_sqft, free_sale_sqft, rehab_sqft, etc.",
                },
                "financial": {
                    "type": "object",
                    "description": "Financial summary: sale_rate_sqft, revenue_crore, cost_crore, profit_crore, roi_percent, etc.",
                },
                # Full microservice outputs (pass entire response dict) - these map to yellow cells
                "site_analysis": {
                    "type": "object",
                    "description": "Full response from analyse_site tool - contains lat/lng, address, area_type, nearby_landmarks",
                },
                "height": {
                    "type": "object",
                    "description": "Full response from get_max_height tool - contains max_height_m, max_floors, aai_zone",
                },
                "premium": {
                    "type": "object",
                    "description": "Full response from calculate_premiums tool - contains construction_cost, mcgm_charges, rr_rates, property_value, line_items",
                },
                "dp_report": {
                    "type": "object",
                    "description": "Full response from get_dp_remarks tool - contains zone, road_width, fsi, dp_remarks, reservations",
                },
                "mcgm_property": {
                    "type": "object",
                    "description": "Full response from get_mcgm_property tool - contains area_sqm, centroid, TPS scheme, plot_no",
                },
                "ready_reckoner": {
                    "type": "object",
                    "description": "RR rate details from premium response",
                },
                "zone_regulations": {
                    "type": "object",
                    "description": "Full response from query_regulations tool",
                },
                # Manual inputs for yellow cells not covered by microservices
                "manual_inputs": {
                    "type": "object",
                    "description": "Manual values for specific yellow cells that need user input (e.g., sale_rate_override, cost_overrides)",
                },
                # LLM narrative (optional — runner auto-appends regulatory_sources)
                "llm_analysis": {
                    "type": "string",
                    "description": "Brief text summary of findings and risks",
                },
            },
            "required": ["society_name", "scheme"],
        },
    },
    {
        "name": "query_regulations",
        "description": "Search for specific DCPR 2034 rules, clauses, or MCGM circulars.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Legal/Regulatory query"},
                "scheme": {
                    "type": "string",
                    "description": "Optional scheme name e.g. '33(7)(B)'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_pr_card",
        "description": (
            "Extract a Property Card (or 7/12 / 8A / K-Prat) from the Maharashtra "
            "Mahabhumi Bhulekh land records portal. Automates form filling, CAPTCHA "
            "solving, and image extraction. Returns status, a download URL for the "
            "card image, and location metadata. Use this whenever the user's query "
            "requires property ownership, area, or title details for a Maharashtra plot."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district": {
                    "type": "string",
                    "description": "District name in English, e.g. 'pune', 'nashik', 'thane'",
                },
                "taluka": {
                    "type": "string",
                    "description": "Taluka name in English, e.g. 'Haveli', 'Pune City'",
                },
                "village": {
                    "type": "string",
                    "description": "Village name in English, e.g. 'Narhe', 'Aundh', 'Wakad'",
                },
                "survey_no": {
                    "type": "string",
                    "description": "Survey / CTS / Gat number, e.g. '1', '123', '45/A'",
                },
                "survey_no_part1": {
                    "type": "string",
                    "description": "Part-1 of survey number when it has sub-parts (optional)",
                },
                "property_uid": {
                    "type": "string",
                    "description": "Property UID / ULPIN if already known (optional)",
                },
                "record_of_right": {
                    "type": "string",
                    "enum": ["7/12", "8A", "Property Card", "K-Prat"],
                    "description": "Type of land record. Default: 'Property Card'",
                },
            },
            "required": ["district", "taluka", "village", "survey_no"],
        },
    },
    {
        "name": "get_dp_remarks",
        "description": (
            "Fetch Development Plan (DP 2034) remarks for a Mumbai property from MCGM's online "
            "portal. Returns the official DP zone (R1/C1/G1 etc.), road width, applicable FSI, "
            "height limit, plot reservations (road/garden/school), CRZ designation, and full DP "
            "remarks text. Call this AFTER get_mcgm_property so the centroid lat/lng can be "
            "passed for a precise spatial zone lookup."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ward": {
                    "type": "string",
                    "description": "BMC ward letter, e.g. 'G/S'",
                },
                "village": {
                    "type": "string",
                    "description": "Village or division name, e.g. 'WORLI'",
                },
                "cts_no": {
                    "type": "string",
                    "description": "CTS or FP number (depending on scheme)",
                },
                "use_fp_scheme": {
                    "type": "boolean",
                    "description": "If true, search as FP (2034 scheme) instead of CTS (1991)",
                },
                "lat": {
                    "type": "number",
                    "description": "Centroid latitude from MCGM property lookup (preferred)",
                },
                "lng": {
                    "type": "number",
                    "description": "Centroid longitude from MCGM property lookup (preferred)",
                },
            },
            "required": ["ward", "village", "cts_no"],
        },
    },
    {
        "name": "get_mcgm_property",
        "description": (
            "Query the MCGM (Municipal Corporation of Greater Mumbai) ArcGIS portal "
            "to look up a property by ward, village, and CTS/CS number. Returns the "
            "official TPS scheme name, Final Plot number, polygon boundary (WGS84), "
            "centroid coordinates, plot area in sqm, and CTS numbers of adjacent properties. "
            "Use this as the FIRST step to get authoritative spatial data for any Mumbai property."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ward": {
                    "type": "string",
                    "description": "BMC ward letter, e.g. 'A', 'B', 'G/N', 'G/S'",
                },
                "village": {
                    "type": "string",
                    "description": "Village or division name, e.g. 'MANDVI', 'WORLI', 'PRABHADEVI'",
                },
                "cts_no": {
                    "type": "string",
                    "description": "CTS or CS number, e.g. '100', '1128', '45/A'",
                },
                "include_nearby": {
                    "type": "boolean",
                    "description": "Whether to also fetch adjacent property CTS numbers (default true)",
                },
            },
            "required": ["ward", "village", "cts_no"],
        },
    },
]



