# Report Generator Service

The final assembly line. Responsible for injecting multi-source data into professional Excel and PDF feasibility reports.

## 📂 Service Structure

```text
├── core/             # Configuration and Constants
├── feasibility/      # Complex calculation logic (secondary metrics)
├── mappings/         # YAML-based Excel cell mappings
├── routers/          # FastAPI API Endpoints
├── schemas/          # Pydantic Request/Response models
├── scripts/          # Expiry alerts and mapping utilities
├── services/         # Business logic (Excel Builder, PDF Converter)
├── templates/        # Master Excel (.xlsx) templates
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
The API will be available at `http://localhost:8004`.

## 🎯 Features
- **Excel Templating:** Uses `openpyxl` to fill complex financial spreadsheets.
- **Formula Calculation:** Computes metrics (Incentives, BUA) using Python.
- **PDF Conversion:** Automated high-quality PDF exports.
- **Expiry Tracking:** Monitors mapping YAMLs for hardcoded constants.

## 🛠️ Tech Stack
- **FastAPI**
- **openpyxl** (Excel engine)
- **dhara_shared** (Strictly typed Dossiers)
- **ReportLab / LibreOffice** (PDF engine)
