# Orchestrator Service - Dhara AI Redevelopment Platform

Main orchestration service that coordinates all microservices in the Dhara AI redevelopment platform. Acts as the central gateway for user requests, manages workflows, and aggregates data from all backend services.

## Purpose

The Orchestrator is the central hub that:
- Routes user requests to appropriate microservices
- Coordinates multi-service workflows
- Manages user sessions and authentication
- Aggregates data from all services for unified responses
- Handles error recovery and fallback logic

## Architecture

```
+-----------------------------------------------------------------------------+
|                              CLIENT REQUEST                                  |
|                        (Web/Api/Mobile Clients)                             |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                             FastAPI Entry Point                             |
|                          (main.py : 8000)                                   |
+-------------------------------+-----------------------------------------------+
                                  |
              +-------------------+-------------------+
              |                                       |
              v                                       v
+---------------------------+               +---------------------------+
|   Middleware Stack        |               |   Router Layer            |
|   - CORS                  |               |   - Auth                  |
|   - Rate Limiting         |               |   - Projects              |
|   - Request Logging       |               |   - Workflows             |
|   - Response Caching      |               |   - Reports              |
+---------------------------+               +---------------------------+
              |                                       |
              +-------------------+-------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                       Core Services Layer                                   |
|  +------------------+  +------------------+  +-------------------------+  |
|  | Database        |  | Redis Cache      |  | LLM Agent              |  |
|  | (PostgreSQL)    |  | (Session/Cache)   |  | (Claude/Gemini)       |  |
|  +------------------+  +------------------+  +-------------------------+  |
+-------------------------------+-----------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                    Microservice Coordination                                |
+-----------------------------------------------------------------------------+
    |           |            |            |            |            |
    v           v            v            v            v            v
+------+ +--------+ +--------+ +--------+ +--------+ +---------+
|RAG   | |DP      | |Height  | |Premium | |Site    | |Report   |
|Service| |Report  | |Service | |Checker | |Analysis| |Generator|
|8006  | |8008    | |8002    | |8003    | |8001    | |8004     |
+------+ +--------+ +--------+ +--------+ +--------+ +---------+
    |           |            |            |            |            |
    +-----------+------------+------------+------------+------------+
                                  |
                                  v
+-----------------------------------------------------------------------------+
|                              RESPONSE                                        |
|          { project_data, analysis_results, reports [] }                    |
+-----------------------------------------------------------------------------+
```

## Key Components

### 1. Agent System (agent/)
- **LLM Client**: Anthropic Claude / Google Gemini integration
- **Workflow Runner**: Orchestrates multi-step processes
- **Task Planning**: Breaks complex requests into steps

### 2. Database Layer (db/)
- **PostgreSQL**: Primary data store
- **SQLAlchemy**: ORM for data models
- **Alembic**: Database migrations
- **Seeding**: Initial data population

### 3. Router Layer (routers/)
- **Auth Router**: User authentication and authorization
- **Project Router**: Project management
- **Workflow Router**: Workflow execution
- **Report Router**: Report generation requests

### 4. Middleware (core/middleware/)
- **CORS**: Cross-origin resource sharing
- **Rate Limiting**: Request throttling
- **Logging**: Request/response logging
- **Caching**: Redis-based response cache

### 5. Service Clients (services/)
- **HTTP Clients**: Communication with microservices
- **Fallback Logic**: Graceful degradation

## Local Development

### Prerequisites
- Python 3.11+
- PostgreSQL (running locally or Docker)
- Redis (running locally or Docker)
- Claude API key / Google Gemini API key

### Setup
```bash
cd services/orchestrator
uv venv .venv --python 3.11
uv sync

# Start PostgreSQL and Redis
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres
docker run -d -p 6379:6379 redis

# Set environment variables
export DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5432/dev
export REDIS_URL=redis://localhost:6379
export ANTHROPIC_API_KEY=your_key

# Start service
.venv\Scripts\python.exe main.py
```

### Environment Variables (.env)
```
APP_NAME=Dhara AI Orchestrator
APP_VERSION=3.0.0
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/orchestrator_db
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=your_key
GEMINI_API_KEY=your_key
SITE_ANALYSIS_URL=http://localhost:8001
HEIGHT_SERVICE_URL=http://localhost:8002
PREMIUM_CHECKER_URL=http://localhost:8003
REPORT_GENERATOR_URL=http://localhost:8004
PR_CARD_URL=http://localhost:8005
RAG_SERVICE_URL=http://localhost:8006
MCGM_PROPERTY_URL=http://localhost:8007
DP_REPORT_SERVICE_URL=http://localhost:8008
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /auth/login | POST | User login |
| /auth/register | POST | User registration |
| /projects | POST | Create project |
| /projects/{id} | GET | Get project details |
| /workflows/execute | POST | Execute workflow |
| /workflows/status | GET | Workflow status |
| /reports/generate | POST | Generate report |
| /health | GET | Health check |

## Workflow Example

**Input**: "Analyze feasibility for Sunrise Society redevelopment"

1. **Intent Detection**: Identify user wants feasibility analysis
2. **Data Collection**:
   - Query RAG Service for DCPR regulations
   - Query DP Report Service for zone info
   - Query Height Service for permissible height
   - Query Premium Checker for charges
   - Query Site Analysis for nearby amenities
3. **Analysis**: Combine all data for feasibility
4. **Report Generation**: Generate Excel/PDF report

## Docker

```bash
# Full stack
docker compose up -d orchestrator postgres redis
```

## Project Structure

```
orchestrator/
├── main.py                 # FastAPI entry point
├── core/                   # Core configuration
│   ├── config.py          # Settings
│   ├── logging_config.py # Logging setup
│   ├── exceptions.py     # Exception handlers
│   └── middleware.py     # Custom middleware
├── db/                    # Database layer
│   ├── models.py         # SQLAlchemy models
│   ├── session.py        # DB session
│   ├── init_db.py        # Initialization
│   └── seed.py           # Default data
├── agent/                 # AI Agent
│   ├── llm_client.py    # LLM integration
│   ├── runner.py        # Workflow runner
│   └── prompts.py       # Agent prompts
├── routers/              # API endpoints
│   ├── auth_router.py  # Authentication
│   ├── project_router.py # Projects
│   └── workflow_router.py # Workflows
├── services/             # Service clients
│   ├── redis.py         # Redis client
│   └── http_clients.py  # Microservice clients
└── schemas/             # Pydantic models
```