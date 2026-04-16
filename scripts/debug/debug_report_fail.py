import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import sys

# Connect to the HOST-MAPPED port (5435)
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5435/redevelopment_ai"

engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Minimal model def to avoid imports
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
Base = declarative_base()

class FeasibilityReport(Base):
    __tablename__ = "feasibility_reports"
    id = Column(UUID(as_uuid=True), primary_key=True)
    status = Column(String)
    error_message = Column(Text)
    created_at = Column(DateTime)

async def check():
    async with async_session() as db:
        stmt = select(FeasibilityReport).order_by(FeasibilityReport.created_at.desc()).limit(1)
        r = (await db.execute(stmt)).scalar_one_or_none()
        if r:
            print(f"REPORT_ID: {r.id}")
            print(f"STATUS: {r.status}")
            print(f"ERROR: {r.error_message}")
        else:
            print("No report found.")

if __name__ == "__main__":
    asyncio.run(check())
