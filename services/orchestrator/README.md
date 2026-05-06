# Orchestrator Service

The **Orchestrator** is the central Command & Control layer of the platform. It handles the application lifecycle, multi-service orchestration, and acts as the secure entry point for all frontend requests.

## 📂 Service Structure

```text
├── agent/            # AI Agent logic, Prompts (markdown), and Tool Executors
├── alembic/          # Database migration history
├── core/             # Central Config (Pydantic), Security, and Middleware
├── db/               # SQLAlchemy engine, session management, and Mixins
├── models/           # Domain entities (Society, Report, User, AuditLog)
├── repositories/     # Data Access Layer (PostgreSQL interaction logic)
├── routers/          # FastAPI API Endpoints (separated by domain)
├── schemas/          # Pydantic Request/Response models
├── services/         # Business logic services (SocietyService, AdminService)
└── main.py           # Application entry point & lifespan management
```

## 🚀 Isolated Execution (Local Dev)

To run the orchestrator in isolation for development:

### 1. Configure Environment
Ensure `.env` exists in this directory with valid credentials.
```bash
# Relative path to root .env is supported via Pydantic Settings
cp .env.example .env
```

### 2. Sync Dependencies
```bash
uv sync
```

### 3. Apply Migrations
```bash
uv run alembic upgrade head
```

### 4. Launch Service
```bash
uv run python -m services.orchestrator.main
```
The API will be available at `http://localhost:8000`.

## 🛠️ Key Architectural Decisions
- **Repository Pattern:** Logic for database queries is decoupled from business services to allow easier testing and DB optimization.
- **Background Tasks:** Heavy AI Agent runs are enqueued via FastAPI `BackgroundTasks` to keep the API responsive.
- **Deep Health:** The `/health` check verifies the reachability of every spoke microservice.

## ✅ PMC Verification APIs

PMC-only routes for verifying Licensed Surveyor (LS) and Architect registrations. These endpoints first delegate registration-number extraction to the OCR service, then perform verification upstream.

- Base path: `/api/verify`
- Auth: PMC or admin role required
- Upload types: `application/pdf`, `image/jpeg`, `image/jpg`, `image/png`, `image/webp`
- Max upload size: 15 MB

Endpoints:

1. POST `/api/verify/license-surveyor`
   - Form: `file` (PDF or image)
   - Response: `{ valid, expired, consultant, total, extractedRegistrationNumber, usedOcr }`

2. POST `/api/verify/architect`
   - Form: `file` (PDF or image)
   - Response: `{ valid, details, extractedRegistrationNumber, usedOcr }`

Example (PowerShell):

```powershell
$TOKEN = "<PMC_OR_ADMIN_JWT>"
Invoke-WebRequest -UseBasicParsing -Method Post \
  -Headers @{ Authorization = "Bearer $TOKEN" } \
  -ContentType "multipart/form-data" \
  -InFile "C:\path\to\certificate.pdf" \
  -Uri http://localhost:8000/api/verify/architect
```

Notes:
- OCR strategy defaults to auto: extract PDF text-layer first, then OCR fallback.
- Timeouts for upstream scraping/verification honor `SCRAPE_TIMEOUT_MS` (default 45000 ms).
