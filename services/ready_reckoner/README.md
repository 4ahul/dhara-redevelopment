# Ready Reckoner Service - Government Charges Calculator

Microservice for calculating MCGM premiums, taxes, and government charges based on Ready Reckoner (RR) rates.

## Purpose

- RR Rate lookup for any ward/village in Mumbai
- Calculation of Staircase/Lift/Lobby premiums
- Fungible FSI premium calculation
- Open Space Deficiency (OSD) charges

## Architecture

+-----------------------------------------------------------------------------+
|                             FastAPI Entry Point                             |
|                              (main.py : 8003)                               |
+-------------------------------+-----------------------------------------------+

## Local Development

### Setup
```bash
cd services/ready_reckoner
uv venv .venv --python 3.11
uv sync
.venv\Scripts\python.exe main.py
```

## Docker

```bash
docker compose up -d ready_reckoner
```
