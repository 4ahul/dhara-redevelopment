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
