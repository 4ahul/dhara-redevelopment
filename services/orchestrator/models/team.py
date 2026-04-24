import uuid
from datetime import datetime

from db.base import Base
from models.enums import InviteStatus, TenderStatus
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


def _uuid():
    return uuid.uuid4()

def _now():
    return datetime.utcnow()


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    organization: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(100), nullable=False, default="member")
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    invite_token: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    status: Mapped[InviteStatus] = mapped_column(
        SAEnum(InviteStatus, name="invite_status", create_constraint=True),
        default=InviteStatus.PENDING, nullable=False,
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    user = relationship("User", foreign_keys=[user_id], back_populates="team_memberships")
    inviter = relationship("User", foreign_keys=[invited_by], lazy="selectin")

    __table_args__ = (UniqueConstraint("email", "organization", name="uq_team_email_org"),)


class SocietyTender(Base):
    __tablename__ = "society_tenders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[TenderStatus] = mapped_column(
        SAEnum(TenderStatus, name="tender_status", create_constraint=True),
        default=TenderStatus.DRAFT, nullable=False,
    )
    awarded_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    society = relationship("Society", back_populates="tenders")
    awarded_user = relationship("User", foreign_keys=[awarded_to], lazy="selectin")


