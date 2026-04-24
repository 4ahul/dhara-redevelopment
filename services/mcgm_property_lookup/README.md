# MCGM Property Lookup Service - ArcGIS Property Data

Microservice for retrieving property-related information from MCGM's ArcGIS spatial database, including ownership details, property boundaries, and land use classification.

## Purpose

Queries MCGM's geographic information system to retrieve:
- Property ownership information
- Survey number / CTS number details
- Property boundary polygons
- Land use classification
- Ward and zone information

## Architecture

```
+-----------------------------------------------------------------------------+
|                              CLIENT REQUEST                                  |
|              { address, survey_no, cts_no, latitude, longitude }          |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                             FastAPI Entry Point                             |
|                              (main.py : 8008)                               |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                     Startup Layer Discovery                                  |
|  +-----------------------------------------------------------------------+  |
|  |  ArcGIS Discovery: mcgm.maps.arcgis.com                             |  |
|  |  - Search for property layers                                        |  |
|  |  - Discover MapServer/13 (Property Layer)                           |  |
|  |  - Fallback: hardcoded layer URL                                    |  |
|  +-----------------------------------------------------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                    Property Lookup Handler                                   |
|  +------------------+  +------------------+  +-------------------------+  |
|  | Address Match   |  | Spatial Query    |  | Attribute Retrieval     |  |
|  | (geocoding)     |  | (point/polygon)  |  | (owner, survey, etc)   |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
              +-------------------+-------------------+
              |                                       |
              v                                       v
+---------------------------+               +---------------------------+
|     ArcGIS API (Primary)  |               |  Playwright (Fallback)   |
|   Direct layer queries    |               |   Browser automation     |
+---------------------------+               +---------------------------+
              |                                       |
              +-------------------+-------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                              RESPONSE                                        |
|   { property_details { owner, survey_no, cts_no, area, boundary },         |
|     ward, zone, land_use }                                                  |
+-----------------------------------------------------------------------------+
```

## Key Components

### 1. ArcGIS Client (services/arcgis_client.py)
- **Layer Discovery**: Searches ArcGIS for property layers
- **Query Execution**: SPATIAL / ATTRIBUTE queries
- **Fallback Mechanism**: Browser scraper if API fails

### 2. Property Router (routers/)
- **/property/by-address**: Lookup by street address
- **/property/by-survey**: Lookup by survey number
- **/property/by-cts**: Lookup by CTS number
- **/property/by-coords**: Lookup by lat/long

### 3. Geocoding Service (services/geocoding.py)
- **Address Standardization**: Normalize Mumbai addresses
- **Coordinate Conversion**: Address to lat/long

## Local Development

### Prerequisites
- Python 3.11+
- Internet connection (for ArcGIS queries)

### Setup
```bash
cd services/mcgm_property_lookup
uv venv .venv --python 3.11
uv sync

# Start service
.venv\Scripts\python.exe main.py
```

### Environment Variables (.env)
```
APP_NAME=MCGM Property Lookup
APP_VERSION=1.0.0
ARCGIS_TIMEOUT=30
ARCGIS_SEARCH_URL=https://mcgm.maps.arcgis.com
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /property/by-address | POST | Lookup by address |
| /property/by-survey | POST | Lookup by survey number |
| /property/by-cts | POST | Lookup by CTS number |
| /property/by-coords | POST | Lookup by coordinates |
| /health | GET | Health check |

## Query Flow Example

**Input**: `{ "address": "Near Khar Police Station, Khar West, Mumbai" }`

1. **Geocoding**: Convert address to coordinates
2. **Layer Query**: Query ArcGIS Property MapServer
3. **Feature Extraction**: Get property polygon
4. **Attribute Query**: Retrieve owner, survey number

**Output**:
```json
{
  "property_details": {
    "owner": "XYZ Cooperative Housing Society",
    "cts_no": "1/1234",
    "survey_no": "85/1",
    "area_sqmt": 2500,
    "boundary": {...}
  },
  "ward": "Khar Ward",
  "zone": "Western Suburbs",
  "land_use": "Residential"
}
```

## Docker

```bash
docker compose up -d mcgm_property_lookup
```

## Project Structure

```
mcgm_property_lookup/
├── main.py                 # FastAPI entry point
├── core/                   # Configuration
├── routers/                # API endpoints
├── services/               # Business logic
│   ├── arcgis_client.py   # ArcGIS integration
│   └── geocoding.py       # Address geocoding
├── schemas/                # Pydantic models
└── tests/                  # Unit tests
```