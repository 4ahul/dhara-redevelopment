# DP Remarks Report Service - MCGM Development Plan 2034

Microservice for retrieving Development Plan (DP) zone information and regulatory remarks for Mumbai properties.

## Purpose

Queries MCGM (Municipal Corporation of Greater Mumbai) Development Plan 2034 ArcGIS services to determine:
- DP Zone classification (Residential, Commercial, Industrial, etc.)
- Zoning regulations and permissible uses
- FSI (Floor Space Index) norms
- Building height restrictions

## Architecture

+-----------------------------------------------------------------------------+
|                             FastAPI Entry Point                             |
|                              (main.py : 8008)                               |
+-------------------------------+-----------------------------------------------+

## Local Development

### Setup
```bash
cd services/dp_remarks_report
uv venv .venv --python 3.11
uv sync
.venv\Scripts\python.exe main.py
```

## Docker

```bash
docker compose up -d dp_remarks_report
```
