# PR Card Scraper Service

Retrieves official Property Register (PR) Cards from the Mahabhumi portal to verify title and area.

## 📂 Service Structure

```text
├── core/             # Configuration and App settings
├── routers/          # FastAPI API Endpoints
├── schemas/          # Pydantic models
├── services/         # Business logic (Playwright & Vision solvers)
└── main.py           # Application entry point
```

## 🚀 Isolated Execution (Local Dev)

To run this service in isolation for development:

1. **Configure Environment**
   ```bash
   cp .env.example .env
   # Add GEMINI_API_KEY for CAPTCHA solving
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
The API will be available at `http://localhost:8005`.

## 🎯 Features
- **Title Verification:** Verifies legal owner names and tenure.
- **CAPTCHA Solver:** Leverages LLM Vision APIs to solve portal captchas.

## 🛠️ Tech Stack
- **Playwright**
- **Gemini / OpenAI Vision**
- **dhara_shared**
