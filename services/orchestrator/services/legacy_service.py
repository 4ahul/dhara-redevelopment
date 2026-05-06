"""
Legacy Service — Backward compatibility for session-based Redis storage.
"""

import logging
import uuid

from fastapi import HTTPException

from services.orchestrator.schemas import (
    ChatMessage,
    SessionCreate,
    SessionResponse,
    UserProfileResponse,
    UserProfileUpdate,
)
from services.orchestrator.services.redis import (
    delete_session,
    get_session,
    get_user_profile,
    get_user_sessions,
    save_session,
    save_user_profile,
    update_session_report,
)

logger = logging.getLogger(__name__)


class LegacyService:
    def __init__(self, db=None):
        # db is not used for Redis-based legacy service but kept for dependency consistency
        self.db = db

    async def create_session(self, user_id: str, req: SessionCreate) -> SessionResponse:
        session_id = str(uuid.uuid4())
        if save_session(session_id, user_id, req.model_dump()):
            return SessionResponse(
                session_id=session_id, status="created", message="Session created successfully"
            )
        raise HTTPException(500, "Failed to create session")

    async def list_sessions(self, user_id: str) -> dict:
        sessions = get_user_sessions(user_id)
        return {"sessions": sessions, "count": len(sessions)}

    async def get_session_detail(self, session_id: str, user_id: str) -> dict:
        data = get_session(session_id, user_id)
        if not data:
            raise HTTPException(404, "Session not found")
        return {"session_id": session_id, **data}

    async def generate_for_session(self, session_id: str, user_id: str) -> dict:
        data = get_session(session_id, user_id)
        if not data:
            raise HTTPException(404, "Session not found")

        # Lazy import to avoid circular dependency
        from services.orchestrator.agent import run_agent

        result = await run_agent(data)

        if result.get("report_path"):
            update_session_report(session_id, user_id, result["report_path"])

        return result

    async def chat_update(self, session_id: str, user_id: str, req: ChatMessage) -> dict:
        data = get_session(session_id, user_id)
        if not data:
            raise HTTPException(404, "Session not found")

        for mod in req.modifications:
            data[mod["field"]] = mod["value"]

        from services.orchestrator.agent import run_agent

        result = await run_agent(data)
        save_session(session_id, user_id, data)

        return {
            "session_id": session_id,
            "message": req.message,
            "modifications": req.modifications,
            "result": result,
        }

    async def delete_session(self, session_id: str, user_id: str) -> dict:
        if not delete_session(session_id, user_id):
            raise HTTPException(404, "Session not found")
        return {"status": "deleted", "session_id": session_id}

    async def get_user_profile(self, user_id: str) -> UserProfileResponse:
        p = get_user_profile(user_id)
        return UserProfileResponse(
            id=user_id,
            name=p.get("name"),
            email=p.get("email"),
            phone=p.get("phone"),
            organization=p.get("organization"),
        )

    async def update_user_profile(self, user_id: str, req: UserProfileUpdate) -> dict:
        data = req.model_dump(exclude_unset=True)
        if data:
            save_user_profile(user_id, data)
        return {"status": "updated", "user_id": user_id}

    async def get_user_reports(self, user_id: str) -> dict:
        sessions = get_user_sessions(user_id)
        reports = [
            {
                "session_id": s.get("session_id"),
                "report_path": s.get("data", {}).get("report_path"),
                "created_at": s.get("created_at"),
            }
            for s in sessions
            if s.get("data", {}).get("report_path")
        ]
        return {"reports": reports, "count": len(reports)}
