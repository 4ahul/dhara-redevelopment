"""WebSocket Routes — Refactored version using AgentService"""

import asyncio
import logging

from core.dependencies import get_agent_service
from core.security import decode_token
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from services.agent_service import AgentService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


def _auth_ws(token: str) -> dict | None:
    if not token:
        return None
    try:
        return decode_token(token)
    except Exception:
        return None


@router.websocket("/ws/agent/{session_id}")
async def ws_pmc(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(""),
    service: AgentService = Depends(get_agent_service)
):
    if not _auth_ws(token):
        await websocket.close(code=4001, reason="Auth required")
        return

    await service.mgr.connect(session_id, websocket)
    await service.mgr.send(websocket, {"type": "status", "status": "connected", "session_id": session_id})

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") == "ping":
                await service.mgr.send(websocket, {"type": "pong"})
            elif data.get("action") == "start":
                sd = data.get("data", {})
                if not sd.get("society_name"):
                    await service.mgr.send(websocket, {"type": "error", "message": "Missing society_name"})
                    continue
                asyncio.create_task(service.run_agent_ws(session_id, sd))
            else:
                await service.mgr.send(websocket, {"type": "error", "message": f"Unknown action: {data.get('action')}"})
    except WebSocketDisconnect:
        service.mgr.disconnect(session_id, websocket)


@router.websocket("/ws/admin/agent/{session_id}")
async def ws_admin(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(""),
    service: AgentService = Depends(get_agent_service)
):
    payload = _auth_ws(token)
    if not payload:
        await websocket.close(code=4001, reason="Auth required")
        return
    if payload.get("role") != "admin":
        await websocket.close(code=4003, reason="Admin required")
        return

    await service.mgr.connect(session_id, websocket)
    await service.mgr.send(websocket, {"type": "status", "status": "connected", "session_id": session_id})

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") == "ping":
                await service.mgr.send(websocket, {"type": "pong"})
            elif data.get("action") == "start":
                sd = data.get("data", {})
                if not sd.get("society_name"):
                    await service.mgr.send(websocket, {"type": "error", "message": "Missing society_name"})
                    continue
                asyncio.create_task(service.run_agent_ws(session_id, sd))
            else:
                await service.mgr.send(websocket, {"type": "error", "message": f"Unknown action: {data.get('action')}"})
    except WebSocketDisconnect:
        service.mgr.disconnect(session_id, websocket)


