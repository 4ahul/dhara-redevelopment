# Site Analysis Service

Specialized worker for geocoding, area classification, and landmark discovery.

## 📂 Service Structure

```text
├── core/             # Central Config and Pydantic Settings
├── routers/          # FastAPI API Endpoints
├── schemas/          # Pydantic Request/Response models
├── services/         # Business logic (Google Maps integration)
└── main.py           # Application entry point
```

## 🚀 Isolated Execution (Local Dev)

To run this service in isolation for development:

1. **Configure Environment**
   ```bash
   cp .env.example .env
   # Add your GOOGLE_MAPS_API_KEY
   ```

2. **Sync Dependencies**
   ```bash
   uv sync
   ```

3. **Launch Service**
   ```bash
   uv run python main.py
   ```
The API will be available at `http://localhost:8001`.

## 🎯 Primary Features
- **Geocoding:** Resolves raw addresses into precise Lat/Lng coordinates using Google Maps.
- **Zone Inference:** Identifies MCGM zone categories (Residential, Commercial, etc.).
- **Landmark Discovery:** Finds nearby hospitals, parks, and schools for neighborhood context.

## 🛠️ Tech Stack
- **Google Maps SDK**
- **dhara_shared** (Logging, Exceptions)
- **FastAPI**
