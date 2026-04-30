import uuid

from services.orchestrator.db.base import Base
from services.orchestrator.db.mixins import TimestampMixin, UUIDMixin
from services.orchestrator.models.enums import ReportStatus
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class SocietyReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "society_reports"

    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False, default="feasibility")
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cloudinary_public_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, name="report_status", create_constraint=True),
        default=ReportStatus.PENDING, nullable=False,
    )
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    society = relationship("Society", back_populates="reports")


class FeasibilityReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "feasibility_reports"

    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="Feasibility Report")
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cloudinary_public_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, name="report_status", create_constraint=True),
        default=ReportStatus.PENDING, nullable=False,
    )
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_log: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    llm_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # FE summary fields (populated from output_data after report generation)
    feasibility: Mapped[str | None] = mapped_column(String(20), nullable=True, default="pending")
    fsi: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_value: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plot_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    existing_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposed_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structural_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    completion_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    society = relationship("Society", back_populates="feasibility_reports")
    user = relationship("User", back_populates="feasibility_reports")

    __table_args__ = (
        Index("ix_feasibility_user", "user_id"),
        Index("ix_feasibility_society", "society_id"),
        Index("ix_feasibility_created_at", "created_at"),
    )




