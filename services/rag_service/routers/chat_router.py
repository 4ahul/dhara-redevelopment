import os
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, BackgroundTasks
from fastapi.responses import StreamingResponse

from db.session import get_db
from core.dependencies import require_auth
from schemas.chat import ChatMessageRequest

# Late imports to avoid circular dependencies
def get_rag_agent():
    from services.intelligent_rag import SessionRAG
    return SessionRAG(session_id="global")

router = APIRouter(prefix="/api", tags=["Chat"])
logger = logging.getLogger(__name__)

@router.post("/chat")
async def chat_sync(
    request: ChatMessageRequest,
    authorization: str = Header(None),
    token: Optional[str] = Query(None),
    db=Depends(get_db),
):
    """
    Query the trained system with DCPR & other regulations.
    Matches Excel task: 'Train system with DCPR & other regulations'
    """
    payload = require_auth(authorization, token, db)
    user_id = int(payload["sub"])

    # Fast path for greetings
    msg = request.message.strip().lower()
    if msg in ["hi", "hello", "hey"] or msg.startswith("good "):
        return {"content": "Hello! How can I help you today?", "sources": [], "clauses": []}

    from services.intelligent_rag import SessionRAG
    agent = SessionRAG(session_id=request.session_id or "global")
    
    full_content = ""
    sources = []
    
    for chunk_str in agent.stream_query(request.message, session_id=request.session_id):
        try:
            data = json.loads(chunk_str)
            if data.get("type") == "content":
                full_content += data.get("content", "")
            elif data.get("type") == "metadata":
                sources = data.get("sources", [])
        except:
            continue
                
    return {
        "content": full_content,
        "sources": sources
    }

@router.post("/query")
async def query_regulations(request: dict):
    """
    Internal service-to-service endpoint for the orchestrator agent.
    Accepts {"query": str, "scheme": str (optional)} — no auth required.
    Returns {"answer": str, "sources": list, "clauses": list}.
    """
    question = request.get("query", "")
    scheme = request.get("scheme", "")
    if scheme:
        question = f"{question} (scheme: {scheme})"

    if not question.strip():
        return {"answer": "", "sources": [], "clauses": []}

    from services.intelligent_rag import SessionRAG
    import uuid as _uuid
    agent = SessionRAG(session_id=f"orchestrator_{_uuid.uuid4().hex[:8]}")

    full_answer = ""
    sources = []
    clauses = []

    try:
        for chunk_str in agent.stream_query(question):
            try:
                data = json.loads(chunk_str)
                if data.get("type") == "content":
                    full_answer += data.get("content", "")
                elif data.get("type") == "metadata":
                    raw_sources = data.get("sources", [])
                    sources = [
                        {"text": s.get("text", ""), "source": s.get("source", ""), "page": s.get("page")}
                        for s in raw_sources
                    ]
                    # Extract clause references from sources
                    for s in raw_sources:
                        src = s.get("source", "")
                        if src and src not in clauses:
                            clauses.append(src)
            except Exception:
                continue
    except Exception as e:
        logger.error("RAG query error: %s", e)
        return {"answer": "", "sources": [], "clauses": [], "error": str(e)}

    return {"answer": full_answer, "sources": sources, "clauses": clauses}


@router.get("/health")
def health():
    return {"status": "ok", "service": "rag"}
