import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orchestrator.db.base import Base
from orchestrator.models.enums import SocietyStatus


def _uuid():
    return uuid.uuid4()


def _now():
    return datetime.utcnow()


class Society(Base):
    __tablename__ = "societies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    onboarded_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    poc_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    poc_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    poc_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SocietyStatus] = mapped_column(
        SAEnum(SocietyStatus, name="society_status", create_constraint=True),
        nullable=False,
        default=SocietyStatus.NEW,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now, nullable=False
    )

    created_by_user = relationship("User", back_populates="societies", lazy="selectin")
    reports = relationship(
        "SocietyReport", back_populates="society", lazy="selectin", cascade="all, delete-orphan"
    )
    tenders = relationship(
        "SocietyTender", back_populates="society", lazy="selectin", cascade="all, delete-orphan"
    )
    feasibility_reports = relationship(
        "FeasibilityReport", back_populates="society", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_societies_created_by", "created_by"),)
