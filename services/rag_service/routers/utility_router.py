"""Utility endpoints for the RAG service."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["Utility"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "rag_service"}
