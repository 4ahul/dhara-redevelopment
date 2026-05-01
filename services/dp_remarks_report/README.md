# DP Remarks Service

Automated discovery and extraction of MCGM Development Plan (DP) 2034 remarks.

## 📂 Service Structure

```text
├── core/             # Configuration and App settings
├── routers/          # FastAPI API Endpoints
├── schemas/          # Pydantic models
├── services/         # Business logic (Playwright & PDF Parsing)
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
The API will be available at `http://localhost:8008`.

## 🎯 Features
- **PDF Automation:** Navigates the MCGM portal to generate official DP Remark PDFs.
- **Data Extraction:** Parses PDF content for constraints (road width, NOCs).

## 🛠️ Tech Stack
- **Playwright**
- **pypdf**
- **dhara_shared**
