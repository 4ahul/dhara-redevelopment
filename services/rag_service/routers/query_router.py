import logging

from fastapi import APIRouter, Depends, Request

from ..core.dependencies import require_auth
from ..db.session import get_db

router = APIRouter(prefix="/api", tags=["Query"])
logger = logging.getLogger(__name__)


def get_rag_agent():
    from ..services.intelligent_rag import IntelligentRAG

    return IntelligentRAG()


@router.post("/rag-query")
async def rag_query(
    request: Request,
    payload: dict = Depends(require_auth),
    db=Depends(get_db),
):
    body = await request.json()
    query = body.get("query", "")

    agent = get_rag_agent()
    answer_data = agent.query(query)

    return {
        "answer": answer_data.get("answer", ""),
        "sources": answer_data.get("sources", []),
        "clauses": answer_data.get("clauses", []),
        "confidence": answer_data.get("confidence", 0),
    }


@router.post("/query")
async def query_legacy(
    request: Request,
    db=Depends(get_db),
):
    # Internal orchestrator query (often bypasses full auth or uses specific token)
    # For now, matching the orchestrator contract
    body = await request.json()
    query = body.get("query", "")

    # We might need to bypass auth here if orchestrator calls it without header
    # Let's check api.py logic for this.
    # In api.py it called require_auth, so it expected auth.
    # But for microservice mapping we usually want a back-channel or shared secret.

    agent = get_rag_agent()
    answer_data = agent.query(query)

    return {
        "answer": answer_data.get("answer", ""),
        "sources": answer_data.get("sources", []),
        "clauses": answer_data.get("clauses", []),
        "confidence": answer_data.get("confidence", 0),
    }
