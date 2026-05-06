#!/bin/bash
set -e
export PYTHONPATH=/app:/app/services
cd /app

# Detect if schema is ahead of alembic tracking (columns missing despite version recorded).
# If societies.year_built doesn't exist, the migrations from a1b2c3d4e5f6 onward never ran —
# force re-stamp to 299bcff565b9 so upgrade head applies all outstanding migrations.
python - <<'EOF'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from services.orchestrator.core.config import settings

async def fix_version():
    engine = create_async_engine(settings.db_url)
    async with engine.begin() as conn:
        # 1. Ensure all columns required by the baseline exist in feasibility_reports
        # This is necessary because some DBs might have a 'feasibility_reports' table 
        # from a pre-baseline state that is missing these columns.
        cols_to_add = [
            ("ward", "VARCHAR(20)"),
            ("village", "VARCHAR(255)"),
            ("cts_no", "VARCHAR(100)"),
            ("fp_no", "VARCHAR(100)"),
            ("fsi", "DOUBLE PRECISION"),
            ("plot_area", "DOUBLE PRECISION"),
            ("estimated_value", "VARCHAR(100)"),
            ("existing_units", "INTEGER"),
            ("proposed_units", "INTEGER"),
            ("feasibility", "VARCHAR(50) DEFAULT 'pending'")
        ]
        
        for col_name, col_type in cols_to_add:
            res = await conn.execute(text(
                f"SELECT EXISTS (SELECT FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name = 'feasibility_reports' "
                f"AND LOWER(column_name) = '{col_name}')"
            ))
            if not res.scalar():
                print(f"Adding missing column {col_name} to feasibility_reports")
                await conn.execute(text(f"ALTER TABLE feasibility_reports ADD COLUMN {col_name} {col_type}"))

        # 2. Re-stamping logic
        res_tenders = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'tender_proposals')"
        ))
        tenders_exists = res_tenders.scalar()

        res_comm = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'societies' "
            "AND LOWER(column_name) = 'num_commercial')"
        ))
        num_comm_exists = res_comm.scalar()

        res_flats = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'societies' "
            "AND LOWER(column_name) = 'num_flats')"
        ))
        num_flats_still_exists = res_flats.scalar()
        
        res_audit = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'audit_logs')"
        ))
        baseline_exists = res_audit.scalar()

        try:
            res_ver = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            current_version = res_ver.scalar()
        except Exception:
            current_version = None
        
        broken_revisions = {'e1f2a3b4c5d6', '299bcff565b9'}
        
        target_version = None
        if tenders_exists:
            target_version = 'a1b2c3d4e5f6'
        elif not num_flats_still_exists and num_comm_exists:
            target_version = '1225b36ec86b'
        elif num_comm_exists:
            target_version = '5586ce5e7607'
        elif baseline_exists:
            target_version = '821429fd75aa'

        if target_version and (current_version is None or current_version in broken_revisions or current_version != target_version):
            if current_version in broken_revisions or current_version is None:
                await conn.execute(text("DELETE FROM alembic_version"))
                await conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{target_version}')"))
                print(f"SUCCESS: Re-stamped alembic_version to {target_version}")

asyncio.run(fix_version())
EOF

python -m alembic -c services/orchestrator/alembic.ini upgrade head
