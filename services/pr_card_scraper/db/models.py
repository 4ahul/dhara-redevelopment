import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid():
    return uuid.uuid4()


def _now():
    return datetime.utcnow()


class PRCard(Base):
    __tablename__ = "pr_cards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    district: Mapped[str] = mapped_column(Text, nullable=False)
    taluka: Mapped[str] = mapped_column(Text, nullable=False)
    village: Mapped[str] = mapped_column(Text, nullable=False)
    survey_no: Mapped[str] = mapped_column(Text, nullable=False)
    survey_no_part1: Mapped[str | None] = mapped_column(Text, nullable=True)
    mobile: Mapped[str] = mapped_column(Text, nullable=False)

    property_uid: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    tenure: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_rights: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stores PR Card image download URL or path
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Store session/captcha state for retries
    form_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now, nullable=False
    )

    __table_args__ = (Index("ix_pr_cards_lookup", "district", "taluka", "village", "survey_no"),)
