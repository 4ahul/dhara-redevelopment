import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime, Index, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID, JSONB

class Base(DeclarativeBase):
    pass

def _uuid():
    return uuid.uuid4()

def _now():
    return datetime.utcnow()

class PropertyLookup(Base):
    __tablename__ = "property_lookups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ward: Mapped[str] = mapped_column(Text, nullable=False)
    village: Mapped[str] = mapped_column(Text, nullable=False)
    cts_no: Mapped[str] = mapped_column(Text, nullable=False)
    tps_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    fp_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    centroid_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry_wgs84: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    nearby_properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    map_screenshot: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (
        Index("ix_property_lookups_ward_village_cts", "ward", "village", "cts_no"),
    )

