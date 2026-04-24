# RAG Service

Intelligent Chatbot engine capable of answering complex regulatory questions about DCPR 2034.

## 📂 Service Structure

```text
├── core/             # Configuration and App lifespan
├── db/               # PostgreSQL session and chat models
├── data/             # Regulatory source documents (PDFs)
├── integrations/     # External LLM and Vector DB connections
├── routers/          # FastAPI API Endpoints
├── schemas/          # Pydantic models
├── services/         # LangGraph reasoning and search logic
└── main.py           # Application entry point
```

## 🚀 Isolated Execution (Local Dev)

To run this service in isolation for development:

1. **Configure Environment**
   ```bash
   cp .env.example .env
   # Add GEMINI_API_KEY or OPENAI_API_KEY
   ```

2. **Sync Dependencies**
   ```bash
   uv sync
   ```

3. **Database Initialization**
   ```bash
   uv run alembic upgrade head
   ```

4. **Launch Service**
   ```bash
   uv run python main.py
   ```
The API will be available at `http://localhost:8006`.

## 🎯 Features
- **Regulatory RAG:** Semantic search across development notifications.
- **Milvus Integration:** Vector search for document grounding.
- **LangGraph Orchestration:** Multi-step agent reasoning.

## 🛠️ Tech Stack
- **LangChain / LangGraph**
- **Milvus** (Vector DB)
- **SQLAlchemy + Alembic**
- **dhara_shared** (Unified Logging)
