import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Header, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from db.session import get_db, User, ChatSession, Message, FeedbackLog, SessionLocal
from core.dependencies import require_auth
from schemas.chat import ChatMessageRequest, EditMessageRequest, FeedbackRequest, CreateSessionRequest

router = APIRouter(prefix="/api", tags=["Chat"])
logger = logging.getLogger(__name__)

STREAM_TIMEOUT_SECONDS = 120

def sanitize_session_title(message: str) -> str:
    title = message.strip()[:50]
    if len(message.strip()) > 50:
        title += "..."
    return title or "New Chat"

def get_rag_agent():
    from services.intelligent_rag import IntelligentRAG
    return IntelligentRAG()

def _save_chat_messages(
    session_db_id: int,
    session_id: str,
    user_content: str,
    assistant_content: str,
    answer_sources: list,
    answer_confidence: float,
    thought_process: list,
    update_title: bool = False,
    new_title: str = None,
):
    db = SessionLocal()
    try:
        clean_answer = assistant_content
        clean_answer = re.sub(r"^#{1,6}\s+", "", clean_answer, flags=re.MULTILINE)
        clean_answer = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean_answer)
        clean_answer = re.sub(r"\*([^*]+)\*", r"\1", clean_answer)
        clean_answer = re.sub(r"`([^`]+)`", r"\1", clean_answer)
        clean_answer = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_answer)
        clean_answer = re.sub(r"^[-*+]\s+", "", clean_answer, flags=re.MULTILINE)
        clean_answer = re.sub(r"^\d+\.\s+", "", clean_answer, flags=re.MULTILINE)
        clean_answer = re.sub(r"\n{3,}", "\n\n", clean_answer).strip()

        user_msg = Message(session_id=session_id, role="user", content=user_content)
        asst_msg = Message(
            session_id=session_id,
            role="assistant",
            content=clean_answer,
            sources=json.dumps(answer_sources),
            extra_data=json.dumps(
                {"confidence": answer_confidence, "thought_process": thought_process}
            ),
        )
        db.add(user_msg)
        db.add(asst_msg)

        if update_title and new_title:
            session_obj = (
                db.query(ChatSession).filter(ChatSession.id == session_id).first()
            )
            if session_obj and session_obj.title == "New Chat":
                session_obj.title = new_title
            if session_obj:
                session_obj.last_message_at = datetime.now(timezone.utc)

        db.commit()
        logger.info(f"[DB] Messages saved to session {session_id}")
    except Exception as db_err:
        logger.error(f"[DB] Error saving messages: {db_err}", exc_info=True)
    finally:
        db.close()

@router.get("/sessions")
async def list_sessions(
    payload: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    user_id = payload["sub"]

    rows = (
        db.query(ChatSession, sa_func.count(Message.id).label("message_count"))
        .outerjoin(Message, Message.session_id == ChatSession.id)
        .filter(ChatSession.user_id == user_id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.last_message_at.desc())
        .all()
    )

    return [
        {
            "id": s.id,
            "session_id": s.id,
            "title": s.title,
            "message_count": msg_count,
            "last_message_at": s.last_message_at.isoformat()
            if s.last_message_at
            else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s, msg_count in rows
    ]

@router.post("/sessions")
async def create_session(
    request: CreateSessionRequest = None,
    payload: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    user_id = payload["sub"]
    session_id = str(uuid.uuid4())[:8] # Simplified generate_session_id
    title = request.title if request and request.title else "New Chat"
    is_incognito = False if request else False

    session = ChatSession(
        id=session_id,
        user_id=user_id,
        title=title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "id": session.id,
        "session_id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
    }

@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    payload: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    user_id = payload["sub"]

    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted == False,
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    total = (
        db.query(sa_func.count(Message.id))
        .filter(Message.session_id == session.id)
        .scalar()
    )

    messages = (
        db.query(Message)
        .filter(Message.session_id == session.id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "session_id": session.id,
        "title": session.title,
        "is_incognito": False,
        "total_messages": total,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources) if m.sources else None,
                "clauses": json.loads(m.clauses) if m.clauses else None,
                "metadata": json.loads(m.extra_data) if m.extra_data else None,
                "feedback": m.feedback,
                "edited_at": m.edited_at.isoformat() if m.edited_at else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }

@router.post("/chat/stream")
async def chat_stream(
    request: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    payload: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    user_id = payload["sub"]

    # Check for greetings - fast path
    msg = request.message.strip().lower()
    greetings = ["hi", "hello", "hey", "hiya", "hola", "hii"]
    if (
        msg in greetings
        or msg.startswith("good ")
        or msg in ["help", "who are you", "what is your name"]
    ):
        response = "Hello! How can I help you today?"
        if msg.startswith("good morning"):
            response = "Good morning! Ready to assist you."
        elif msg.startswith("good afternoon"):
            response = "Good afternoon! Ready to assist you."
        elif msg.startswith("good evening"):
            response = "Good evening! Ready to assist you."
        elif msg in ["help", "what can you do", "how can you help"]:
            response = "I can help with building regulations, FSI calculations, premium charges, property feasibility & more. Just ask!"
        elif msg in ["who are you", "what is your name", "tell me about yourself"]:
            response = "I'm your urban planning assistant - I can help with regulations, property feasibility, and building permissions."

        async def greeting_stream():
            yield f"data: {json.dumps({'type': 'thought_process', 'steps': ['Processing query...']})}\n\n"
            yield f"data: {json.dumps({'type': 'content', 'content': response})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'sources': [], 'thought_process': []})}\n\n"

        return StreamingResponse(greeting_stream(), media_type="text/event-stream")

    session = None
    if request.session_id:
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.id == request.session_id,
                ChatSession.user_id == user_id,
            )
            .first()
        )

    if not session and not False:
        session_id = str(uuid.uuid4())[:8]
        session = ChatSession(
            id=session_id,
            user_id=user_id,
            title=sanitize_session_title(request.message),
)
        db.add(session)
        db.commit()
        db.refresh(session)

    agent = get_rag_agent()
    final_session = session

    async def event_generator():
        import asyncio
        import traceback

        loop = asyncio.get_event_loop()
        async_q: asyncio.Queue = asyncio.Queue()

        full_answer = ""
        answer_sources = []
        answer_confidence = 0
        thought_process = []

        def produce():
            try:
                for chunk in agent.stream_query(
                    request.message, session_id=request.session_id
                ):
                    asyncio.run_coroutine_threadsafe(async_q.put(chunk), loop)
                asyncio.run_coroutine_threadsafe(async_q.put(None), loop)
            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                asyncio.run_coroutine_threadsafe(
                    async_q.put(json.dumps({"type": "error", "content": str(e)})), loop
                )
                asyncio.run_coroutine_threadsafe(async_q.put(None), loop)

        loop.run_in_executor(None, produce)

        stream_deadline = asyncio.get_event_loop().time() + STREAM_TIMEOUT_SECONDS
        while True:
            remaining = stream_deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                yield json.dumps({"type": "error", "content": "Stream timed out"})
                break
            try:
                item = await asyncio.wait_for(async_q.get(), timeout=remaining)
            except asyncio.TimeoutError:
                yield json.dumps({"type": "error", "content": "Stream timed out"})
                break
            if item is None:
                if final_session:
                    background_tasks.add_task(
                        _save_chat_messages,
                        final_session.id,
                        final_session.id,
                        request.message,
                        full_answer,
                        answer_sources,
                        answer_confidence,
                        thought_process,
                        update_title=True,
                        new_title=sanitize_session_title(request.message),
                    )
                break

            try:
                data = json.loads(item)
                if data.get("type") == "content":
                    full_answer += data.get("content", "")
                elif data.get("type") == "metadata":
                    raw_sources = data.get("sources", [])
                    answer_sources = []
                    for s in raw_sources:
                        if isinstance(s, dict):
                            text = s.get("text", "")
                            text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
                            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
                            text = re.sub(r"\*([^*]+)\*", r"\1", text)
                            text = re.sub(r"`([^`]+)`", r"\1", text)
                            answer_sources.append({"text": text[:500]})
                elif data.get("type") == "final":
                    answer_confidence = data.get("confidence", 0)
                    thought_process = data.get("thought_process", [])
            except Exception:
                pass

            yield item

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/chat")
async def chat(
    request: ChatMessageRequest,
    payload: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    user_id = payload["sub"]

    q_lower = request.message.lower().strip()
    greeting_patterns = [
        (r"^(hi|hello|hey|hiya|hola)$", "Hello! How can I help you today?"),
        (r"^good\s*(morning|afternoon|evening)$", "Good day! Ready to assist you."),
        (
            r"^(who\s*are\s*you|what\s*is\s*your\s*name|tell\s*me\s*about\s*yourself)$",
            "I'm your urban planning assistant - I can help with regulations, property feasibility, and building permissions.",
        ),
        (
            r"^(help|what\s*can\s*you\s*do|how\s*can\s*you\s*help)$",
            "I can help with building regulations, FSI calculations, premium charges, property feasibility & more. Just ask!",
        ),
        (
            r"^(thanks|thank\s*you|thx)$",
            "You're welcome! Let me know if you need anything else.",
        ),
        (r"^(bye|goodbye|see\s*you|tciao)$", "Goodbye! Come back anytime."),
    ]

    for pattern, response in greeting_patterns:
        if re.match(pattern, request.message.strip(), re.IGNORECASE):
            return JSONResponse(
                {
                    "answer": response,
                    "sources": [],
                    "thought_process": [],
                    "confidence": 1.0,
                    "suggestions": [],
                }
            )

    session = None
    if request.session_id:
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.id == request.session_id,
                ChatSession.user_id == user_id,
            )
            .first()
        )

    if not session and not False:
        session_id = str(uuid.uuid4())[:8]
        session = ChatSession(
            id=session_id,
            user_id=user_id,
            title=sanitize_session_title(request.message),
)
        db.add(session)
        db.commit()
        db.refresh(session)

    agent = get_rag_agent()
    answer_data = agent.query(request.message, session_id=request.session_id)

    thought_process = answer_data.get(
        "thought_process",
        [
            f"Analyzing query: '{request.message}'",
            "Searching vector database for relevant clauses",
            "Synthesizing answer based on retrieved documents",
        ],
    )
    answer_data["thought_process"] = thought_process

    if session and not False:
        user_msg = Message(
            session_id=session.id,
            role="user",
            content=request.message,
        )
        asst_msg = Message(
            session_id=session.id,
            role="assistant",
            content=answer_data["answer"],
            sources=json.dumps(answer_data.get("sources", [])),
            clauses=json.dumps(answer_data.get("clauses", [])),
            extra_data=json.dumps(
                {
                    "confidence": answer_data.get("confidence"),
                    "thought_process": thought_process,
                }
            ),
        )
        db.add(user_msg)
        db.add(asst_msg)

        if session.title == "New Chat":
            session.title = sanitize_session_title(request.message)
        session.last_message_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(user_msg)
        db.refresh(asst_msg)

        answer_data["user_message_id"] = user_msg.id
        answer_data["message_id"] = asst_msg.id
        answer_data["session_id"] = session.id
    else:
        answer_data["user_message_id"] = str(uuid.uuid4())
        answer_data["message_id"] = str(uuid.uuid4())
        answer_data["session_id"] = session.id if session else None

    return answer_data

@router.post("/messages/{message_id}/feedback")
async def add_feedback(
    message_id: int,
    feedback: FeedbackRequest,
    payload: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    user_id = payload["sub"]
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    session = db.query(ChatSession).filter(ChatSession.id == message.session_id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    feedback_log = FeedbackLog(
        user_id=user_id,
        message_id=message_id,
        session_id=session.id,
        feedback_type=feedback.feedback_type,
    )
    db.add(feedback_log)
    message.feedback = feedback.feedback_type
    message.feedback_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True}
