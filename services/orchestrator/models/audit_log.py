import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.base import Base


def _uuid():
    return uuid.uuid4()

def _now():
    return datetime.utcnow()


class AuditLog(Base):
    """
    Tracks all AI Agent tool calls, site analysis results, 
    and policy-driven feasibility outcomes for the platform.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_logs_actor_action", "actor_id", "action"),
    )
