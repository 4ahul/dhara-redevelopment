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
    async with engine.connect() as conn:
        # 1. Check for tender_proposals table (Indicator of latest version a1b2c3d4e5f6)
        res_tenders = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='tender_proposals')"
        ))
        tenders_exists = res_tenders.scalar()

        # 2. Check for num_commercial column (Indicator of version 5586ce5e7607)
        res_comm = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_name='societies' AND column_name='num_commercial')"
        ))
        num_comm_exists = res_comm.scalar()
        
        # 3. Check for audit_logs table (Indicator of baseline 821429fd75aa)
        res_audit = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='audit_logs')"
        ))
        baseline_exists = res_audit.scalar()

        # Current recorded version
        res_ver = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        current_version = res_ver.scalar()
        
        broken_revisions = {'e1f2a3b4c5d6', '299bcff565b9'}
        
        # Determine target version to stamp
        target_version = None
        if tenders_exists:
            target_version = 'a1b2c3d4e5f6'
        elif num_comm_exists:
            target_version = '5586ce5e7607'
        elif baseline_exists:
            target_version = '821429fd75aa'

        if target_version and (current_version is None or current_version in broken_revisions or current_version != target_version):
            # Only re-stamp if we are in a broken state or if the schema is ahead of the recorded version
            # But be careful: only stamp if current version is missing or broken.
            if current_version in broken_revisions or current_version is None:
                await conn.execute(text("DELETE FROM alembic_version"))
                await conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{target_version}')"))
                await conn.commit()
                print(f"Re-stamped alembic_version to {target_version} (detected schema state with broken/missing current version)")
            else:
                print(f"Schema status: current_version={current_version}, detected_state={target_version}. No action taken.")
        else:
            print(f"Schema status: current_version={current_version}, tenders_exists={tenders_exists}, num_comm_exists={num_comm_exists}")

asyncio.run(fix_version())
EOF

python -m alembic -c services/orchestrator/alembic.ini upgrade head
