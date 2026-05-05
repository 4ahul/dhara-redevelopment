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
        # Check for audit_logs table (new baseline indicator)
        result = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='audit_logs')"
        ))
        baseline_exists = result.scalar()
        
        # Current version check
        result2 = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        current_version = result2.scalar()
        
        # Broken/Missing revisions that should be re-stamped to new baseline
        broken_revisions = {'e1f2a3b4c5d6', '299bcff565b9'}
        
        if baseline_exists and (current_version is None or current_version in broken_revisions):
            await conn.execute(text("DELETE FROM alembic_version"))
            await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('821429fd75aa')"))
            await conn.commit()
            print(f"Re-stamped alembic_version to 821429fd75aa (detected broken/missing version {current_version})")
        else:
            print(f"Schema status: baseline_exists={baseline_exists}, current_version={current_version}")

asyncio.run(fix_version())
EOF

python -m alembic -c services/orchestrator/alembic.ini upgrade head
