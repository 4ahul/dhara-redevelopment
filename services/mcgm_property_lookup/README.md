# MCGM Property Lookup Service

Authoritative boundary and plot data discovery via the MCGM ArcGIS platform.

## 📂 Service Structure

```text
├── core/             # Configuration and ArcGIS URL discovery
├── routers/          # FastAPI API Endpoints
├── schemas/          # Pydantic models
├── services/         # Business logic (ArcGIS & Browser Scrapers)
└── main.py           # Application entry point
```

## 🚀 Isolated Execution (Local Dev)

To run this service in isolation for development:

1. **Configure Environment**
   ```bash
   cp .env.example .env
   ```

2. **Sync Dependencies**
   ```bash
   uv sync
   uv run playwright install chromium
   ```

3. **Launch Service**
   ```bash
   uv run python main.py
   ```
The API will be available at `http://localhost:8007`.

## 🎯 Features
- **ArcGIS Mapping:** Scrapes the official MCGM portal for plot boundaries.
- **Authoritative Data:** Source of truth for plot area and TPS names.

## 🛠️ Tech Stack
- **Playwright / Playwright-Stealth**
- **ArcGIS REST API Integration**
- **dhara_shared**
