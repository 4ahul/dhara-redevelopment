# Ready Reckoner Service

Retrieves authoritative land and construction rates (Ready Reckoner rates) for Mumbai properties.

## 📂 Service Structure

```text
├── core/             # Central Config and Pydantic Settings
├── routers/          # FastAPI API Endpoints
├── schemas/          # Pydantic Request/Response models
├── services/         # Business logic (RR Rate Lookups)
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
   ```

3. **Launch Service**
   ```bash
   uv run python main.py
   ```
The API will be available at `http://localhost:8003`.

## 🎯 Features
- **Land Rates:** Fetches open land and residential rates by ward/village.
- **Dossier Mapping:** Maps internal keys for direct Excel template injection.

## 🛠️ Tech Stack
- **FastAPI**
- **dhara_shared** (Logging, Caching)
- **Redis Integration:** Caches lookups for high-performance retrieval.
