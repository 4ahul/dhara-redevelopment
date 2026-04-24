# Dhara AI - Microservices Architecture

Unified platform for real estate redevelopment feasibility, regulatory compliance (RAG), and agentic workflow automation.

## System Architecture

The platform consists of a fleet of Python-based microservices coordinated by a central Orchestrator.

| Service | Port | Responsibility |
| :--- | :--- | :--- |
| **Orchestrator** | 8000 | Central agent, tool execution, and session management |
| **Site Analysis** | 8001 | Google Maps integration, address resolution, and proximity checks |
| **Aviation Height** | 8002 | NOCAS building height verification |
| **Ready Reckoner** | 8003 | MCGM premium calculation logic and RR rate lookup |
| **Report Generator** | 8004 | Excel-to-PDF generation, template mapping, and financial modeling |
| **PR Card Scraper** | 8005 | Automated extraction of data from Mahabhoomi PR cards |
| **RAG Service** | 8006 | DCPR 2034 knowledge base, vector search (Milvus), and regulatory QA |
| **MCGM Lookup** | 8007 | Property tax and ward-level attribute discovery |
| **DP Remarks Report** | 8008 | Extraction and parsing of DP Remark PDF documents |

## Getting Started

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)
- Valid API keys for LLMs (OpenAI, Gemini, or Anthropic)

### 2. Setup
Clone the repository and run the setup script:
```bash
# Windows
.\scripts\setup.ps1

# Linux/macOS
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 3. Launch
```bash
docker compose up --build
```

The system will be available at:
- **API Documentation:** http://localhost:8000/docs
- **RAG Dashboard:** http://localhost:8006/docs
- **pgAdmin:** http://localhost:5050

## Project Structure

```text
├── services/               # Microservice implementations
│   ├── orchestrator/       # Central logic and LLM agent
│   ├── rag_service/        # Regulatory knowledge base (refactored)
│   ├── report_generator/   # Excel/PDF engine
│   └── ...                 # Other domain services
├── shared/                 # Shared data models and utilities
├── scripts/                # Setup and utility scripts
├── data/                   # Base data for knowledge graphs
└── docker-compose.yml      # Root composition
```

## Refactored RAG Service Layout

The `rag_service` has been refactored for modularity:
- `main.py`: App entry point and router inclusion.
- `core/`: Middleware, authentication, and dependencies.
- `db/`: Database models and session management.
- `routers/`: Modular API endpoints (chat, docs, query).
- `services/`: Core business logic (RAG engine, OCR, workflows).
- `schemas/`: Pydantic models for validation.

## Testing

Run the full end-to-end simulation:
```bash
python tests/test_full_flow.py
```

## License
Internal Development - Dhara AI.
