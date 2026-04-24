"""
Agent Service — Orchestrates AI agent execution and real-time WebSocket communication.
"""

import logging

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, sid: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(sid, []).append(ws)

    def disconnect(self, sid: str, ws: WebSocket):
        if sid in self.active:
            self.active[sid] = [c for c in self.active[sid] if c != ws]
            if not self.active[sid]:
                del self.active[sid]

    async def broadcast(self, sid: str, msg: dict):
        dead = []
        for ws in self.active.get(sid, []):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(sid, ws)

    async def send(self, ws: WebSocket, msg: dict):
        try:
            await ws.send_json(msg)
        except Exception:
            pass


# Global manager to maintain state across service instances
manager = ConnectionManager()


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.mgr = manager

    async def run_agent_ws(self, session_id: str, society_data: dict):
        """
        Executes the AI agent and streams progress back via WebSocket.
        Delegates all agent logic to run_agent(); this method only handles streaming.
        """
        import uuid as _uuid

        from agent.runner import run_agent

        await self.mgr.broadcast(
            session_id, {"type": "status", "status": "started", "message": "Agent started..."}
        )

        async def _on_progress(event: dict):
            await self.mgr.broadcast(session_id, event)

        try:
            result = await run_agent(
                society_data,
                str(_uuid.uuid4()),
                progress_callback=_on_progress,
            )
            await self.mgr.broadcast(
                session_id,
                {
                    "type": "completed",
                    "status": result.get("status"),
                    "report_path": result.get("report_path"),
                    "summary": result.get("summary", ""),
                    "tool_calls": result.get("tool_calls", 0),
                },
            )
        except Exception as e:
            logger.error("WebSocket agent error for session %s: %s", session_id, e, exc_info=True)
            await self.mgr.broadcast(session_id, {"type": "error", "message": str(e)})


