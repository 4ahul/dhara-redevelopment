# Dhara AI — Mumbai Redeasibility Engine

Dhara AI is a professional-grade, high-performance microservices monorepo designed to automate real estate redevelopment feasibility in Mumbai. It leverages a multi-agent orchestration layer to aggregate data from fragmented government portals and DCPR 2034 regulations.

## 🏗️ System Architecture

The platform is built on a **Modular Monorepo** pattern, ensuring high cohesion and low coupling between domain boundaries.

```text
├── dhara_shared/           # [CORE] Standardized schemas, logging, and HTTP clients
├── docs/                   # [DOCS] API Specs (OpenAPI) and Architecture Diagrams
├── scripts/                # [OPS] Monorepo automation and data export scripts
├── services/               # [SERVICES] Independent domain microservices
│   ├── orchestrator/       # --> Gateway, Auth, and AI Agent (The Brain)
│   ├── site_analysis/      # --> Geocoding and Landmark Discovery
│   ├── aviation_height/    # --> AAI NOCAS Height Compliance
│   ├── ready_reckoner/     # --> Land & Construction Rate Lookups
│   ├── report_generator/   # --> Excel/PDF Assembly & Expiry Alerts
│   ├── rag_service/        # --> DCPR 2034 Legal Knowledge Bot
│   ├── mcgm_property/      # --> ArcGIS authoritative spatial data
│   ├── pr_card_scraper/    # --> Mahabhumi Land Records extraction
│   └── dp_remarks/         # --> Automated DP 2034 Remarks parsing
├── tests/                  # [TESTS] Global Integration and E2E Test Suite
├── Makefile                # [CI/CD] Unified task runner
├── docker-compose.yml      # [INFRA] Production-parity container stack
└── ruff.toml               # [LINT] Project-wide code quality rules
```

## 🚀 Execution Guide (Full Stack)

### 1. Environment Synchronization
Ensure all microservices and the shared library are perfectly synced within the workspace:
```bash
make sync
```

### 2. Database Provisioning
Run migrations for the Orchestrator and stateful services:
```bash
make migrate
```

### 3. Orchestration (Docker)
Launch the entire mesh on the internal `dhara_net` network:
```bash
make up
```

## 🛠️ Service-Level Development

Every service follows a standardized hexagonal-lite structure:
1.  **Routers:** API boundary (FastAPI).
2.  **Services:** Domain business logic.
3.  **Repositories:** Data persistence (PostgreSQL/Redis).
4.  **Core:** Configuration and Dependency Injection.

To run a specific service in isolation for debugging:
```bash
cd services/<service_name>
uv run python main.py
```

## 🔒 Engineering Standards

*   **Observability:** Unified JSON logging for log aggregation (ELK/Datadog compatible).
*   **Resilience:** Every internal call is protected by a circuit-breaker/retry policy via `dhara_shared.http`.
*   **Security:** "Zero Trust" internal networking; all ingress is proxied through the Orchestrator.
*   **Quality:** Enforced 100-character line limit and strict type hinting via Ruff.

---
**Property of Trinetra Labs — System Architected by Dhara AI Team.**
