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
        # Robust check for tender_proposals table
        res_tenders = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'tender_proposals')"
        ))
        tenders_exists = res_tenders.scalar()

        # Robust check for num_commercial column
        res_comm = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'societies' "
            "AND LOWER(column_name) = 'num_commercial')"
        ))
        num_comm_exists = res_comm.scalar()

        # Check if num_flats was ALREADY dropped (indicates version 1225b36ec86b)
        res_flats = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'societies' "
            "AND LOWER(column_name) = 'num_flats')"
        ))
        num_flats_still_exists = res_flats.scalar()
        
        # Check for audit_logs table
        res_audit = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'audit_logs')"
        ))
        baseline_exists = res_audit.scalar()

        # Get current version from alembic_version
        try:
            res_ver = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            current_version = res_ver.scalar()
        except Exception:
            current_version = None
        
        print(f"DEBUG: current={current_version}, tenders={tenders_exists}, comm={num_comm_exists}, flats_exist={num_flats_still_exists}, baseline={baseline_exists}")

        broken_revisions = {'e1f2a3b4c5d6', '299bcff565b9'}
        
        # Determine the furthest version that matches the current schema state
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
            # If current version is broken/missing, or we detected we are actually ahead of what is recorded
            await conn.execute(text("DELETE FROM alembic_version"))
            await conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{target_version}')"))
            print(f"SUCCESS: Re-stamped alembic_version to {target_version}")
        else:
            print(f"NO ACTION: current_version={current_version}, target_detected={target_version}")

asyncio.run(fix_version())
EOF

python -m alembic -c services/orchestrator/alembic.ini upgrade head
