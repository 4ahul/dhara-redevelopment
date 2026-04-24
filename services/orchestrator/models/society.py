import uuid
from datetime import datetime

from db.base import Base
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


def _uuid():
    return uuid.uuid4()

def _now():
    return datetime.utcnow()

class Society(Base):
    __tablename__ = 'societies'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    poc_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    poc_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    poc_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onboarded_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cts_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fp_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tps_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cts_validated: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ward: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    village: Mapped[str | None] = mapped_column(String(255), nullable=True)
    taluka: Mapped[str | None] = mapped_column(String(255), nullable=True)
    district: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plot_area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    plot_area_with_tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    road_width_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_flats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_commercial: Mapped[int | None] = mapped_column(Integer, nullable=True)
    residential_area_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    commercial_area_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    sale_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    society_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    existing_bua_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    pfa_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='active', nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    created_by_user = relationship('User', back_populates='societies', lazy='selectin')
    reports = relationship('SocietyReport', back_populates='society', lazy='selectin', cascade='all, delete-orphan')
    tenders = relationship('SocietyTender', back_populates='society', lazy='selectin', cascade='all, delete-orphan')
    feasibility_reports = relationship('FeasibilityReport', back_populates='society', lazy='selectin', cascade='all, delete-orphan')

    __table_args__ = (Index('ix_societies_created_by', 'created_by'),)


