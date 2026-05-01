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
        result = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_name='societies' AND column_name='year_built')"
        ))
        year_built_exists = result.scalar()
        if not year_built_exists:
            await conn.execute(text("DELETE FROM alembic_version"))
            await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('299bcff565b9')"))
            await conn.commit()
            print("Re-stamped alembic_version to 299bcff565b9 (missing columns detected, will apply outstanding migrations)")
        else:
            result2 = await conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            count = result2.scalar()
            if count == 0:
                await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('299bcff565b9')"))
                await conn.commit()
                print("Stamped alembic_version to 299bcff565b9 (empty table)")
            else:
                print("Schema up to date, no re-stamp needed")

asyncio.run(fix_version())
EOF

python -m alembic -c services/orchestrator/alembic.ini upgrade head
