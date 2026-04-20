# Aviation Height Service - NOCAS Building Height Verification

Microservice for calculating the permissible building height for a given location based on AAI (Airports Authority of India) NOCAS guidelines.

## Purpose

Provides building height verification including:
- Latitude and Longitude based height limits
- Proximity to airport funnels and takeoff paths
- Integration with NOCAS Map data
- Height permissible in meters above mean sea level (AMSL)

## Architecture

+-----------------------------------------------------------------------------+
|                             FastAPI Entry Point                             |
|                              (main.py : 8002)                               |
+-------------------------------+-----------------------------------------------+

## Local Development

### Prerequisites
- Python 3.11+

### Setup
```bash
cd services/aviation_height
uv venv .venv --python 3.11
uv sync
.venv\Scripts\python.exe main.py
```

## Docker

```bash
docker compose up -d aviation_height
```
