# Dhara RAG Service

Microservice for DCPR 2034 knowledge retrieval and regulatory question answering.

## Architecture

This service follows a modular, layered architecture:

- main.py: Application factory and entry point (Port 8006).
- core/: Shared middleware, authentication logic, and dependencies.
- db/: Database models and session management (PostgreSQL).
- routers/: Modular API routes organized by domain:
  - auth_router.py: User registration, login, and OAuth.
  - chat_router.py: RAG-powered chat sessions and feedback.
  - doc_router.py: Document upload and processing.
  - query_router.py: Raw knowledge retrieval for orchestrator tools.
- services/: Core business logic:
  - intelligent_rag.py: Multi-stage RAG agent with thought process.
  - rag.py: Milvus-based vector search and chunking.
  - property_card_workflow.py: OCR and parsing for Land Records.
- schemas/: Pydantic models for request/response validation.

## Features

- Multi-Source RAG: Searches DCPR 2034 PDF documents, knowledge graphs, and cached vectors.
- Hybrid Search: Combines BM25 and Milvus vector search for precision.
- Intelligent Workflows: Specialized logic for PMC, Builders, and Societies.
- OCR Integration: Built-in support for processing scanned property documents.

## Local Development

### Prerequisites
- Python 3.12+
- PostgreSQL
- Milvus (Vector DB)

### Setup
1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install .
   ```
3. Run the service:
   ```bash
   PORT=8006 uvicorn main:app --reload
   ```

## Docker

The service is containerized using the root docker-compose.yml.

```bash
docker compose up -d --build rag_service
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8006/docs
- ReDoc: http://localhost:8006/redoc
