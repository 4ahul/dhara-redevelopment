# Site Analysis Service - Google Maps API Integration

Microservice for analyzing surrounding infrastructure and amenities at a given location using Google Maps API - useful for feasibility studies and site selection.

## Purpose

Provides comprehensive site analysis including:
- Nearby amenities (schools, hospitals, markets, transit)
- Distance to key landmarks
- Traffic and accessibility analysis
- Neighborhood characteristics
- Satellite imagery and terrain data

## Architecture

```
+-----------------------------------------------------------------------------+
|                              CLIENT REQUEST                                  |
|                   { latitude, longitude, radius, analysis_type }          |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                             FastAPI Entry Point                             |
|                              (main.py : 8001)                               |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                       Google Maps API Integration                            |
|  +------------------+  +------------------+  +-------------------------+  |
|  | Places API       |  | Distance Matrix  |  | Geocoding API          |  |
|  | (nearby search)  |  | (travel time)    |  | (address resolution)   |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                      Site Analysis Engine                                    |
|  +------------------+  +------------------+  +-------------------------+  |
|  | Category Filter |  | Distance Calc    |  | Ranking & Scoring      |  |
|  | (education,     |  | (haversine)      |  | (accessibility score) |  |
|  |  health, etc.)  |  |                  |  |                         |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                    Land Use Analysis (ArcGIS)                               |
|  +------------------+  +------------------+  +-------------------------+  |
|  | Zoning Info     |  | Satellite Imagery|  | Terrain Data           |  |
|  | (from dp_report)|  | (Google Static) |  | (elevation, slope)     |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                              RESPONSE                                        |
|   { nearby_places [], accessibility_score, land_use, analysis_summary }   |
+-----------------------------------------------------------------------------+
```

## Key Components

### 1. Site Router (routes/site_router.py)
- **/analyze**: Full site analysis
- **/nearby**: Find nearby places by category
- **/distance**: Calculate distances to landmarks
- **/accessibility**: Accessibility score

### 2. Google Maps Client (services/google_maps_client.py)
- **Places API**: Search nearby businesses, POIs
- **Distance Matrix**: Travel time calculations
- **Geocoding**: Address to coordinates
- **Static Maps**: Generate map images

### 3. Analysis Engine (services/site_analyzer.py)
- **Category Analysis**: Group places by type
- **Scoring Algorithm**: Weighted accessibility score
- **Land Use Correlation**: Combine with DP zone data

## Local Development

### Prerequisites
- Python 3.11+
- Google Maps API key

### Setup
```bash
cd services/site_analysis
uv venv .venv --python 3.11
uv sync

# Set Google Maps API key
export GOOGLE_MAPS_API_KEY=your_api_key

# Start service
.venv\Scripts\python.exe main.py
```

### Environment Variables (.env)
```
APP_NAME=Site Analysis Service
APP_VERSION=1.0.0
GOOGLE_MAPS_API_KEY=your_key_here
DEFAULT_SEARCH_RADIUS=2000
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /analyze | POST | Full site analysis |
| /nearby | POST | Find nearby places |
| /distance | POST | Calculate distances |
| /accessibility | POST | Get accessibility score |
| /health | GET | Health check |

## Query Flow Example

**Input**:
```json
{
  "latitude": 19.076,
  "longitude": 72.8777,
  "radius": 1500,
  "analysis_type": "residential"
}
```

1. **Places Query**: Search nearby within 1500m
2. **Category Grouping**: Group by type (schools, hospitals, etc.)
3. **Distance Calculation**: Calculate distances to each place
4. **Scoring**: Generate accessibility score
5. **Integration**: Combine with DP zone data

**Output**:
```json
{
  "nearby_places": [
    {"type": "school", "name": "DPS", "distance": 500},
    {"type": "hospital", "name": "Breach Candy", "distance": 800}
  ],
  "accessibility_score": 0.85,
  "land_use": "Residential",
  "analysis_summary": "Good for residential development"
}
```

## Docker

```bash
docker compose up -d site_analysis
```

## Project Structure

```
site_analysis/
├── main.py                 # FastAPI entry point
├── core/                   # Configuration
├── routes/                 # API endpoints
│   └── site_router.py     # Site analysis endpoints
├── services/              # Business logic
│   ├── google_maps_client.py # Google Maps API
│   └── site_analyzer.py   # Analysis engine
├── schemas/                # Pydantic models
└── config/                 # Settings
```