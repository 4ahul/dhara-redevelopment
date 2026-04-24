# Aviation Height Service

Calculates the maximum permissible building height based on AAI (Airports Authority of India) NOCAS rules.

## 📂 Service Structure

```text
├── core/             # Central Config and Pydantic Settings
├── routers/          # FastAPI API Endpoints
├── schemas/          # Pydantic Request/Response models
├── services/         # Business logic (Playwright NOCAS Scraper)
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
The API will be available at `http://localhost:8002`.

## 🎯 Features
- **NOCAS Calculation:** Determines building height limits (AMSL and AGL) using headless browser automation.
- **Precision:** Uses coordinate-based lookup to ensure safety compliance.

## 🛠️ Tech Stack
- **Playwright:** Automates browser interaction for NOCAS validation.
- **dhara_shared** (Logging, Schemas)
- **FastAPI**
