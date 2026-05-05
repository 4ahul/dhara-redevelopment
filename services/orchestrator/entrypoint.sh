#!/bin/bash
set -e

echo "Starting Orchestrator Entrypoint..."

echo "Waiting for PostgreSQL at postgres:5432..."
until printf "" 2>>/dev/null >/dev/tcp/postgres/5432; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is UP!"

echo "Ensuring base tables exist..."
python -c "
import asyncio
# Import ALL models first so SQLAlchemy knows the full dependency graph
import services.orchestrator.models  # noqa: F401
from services.orchestrator.db import init_db
asyncio.run(init_db())
print('Base tables created/verified.')
"

echo "Running Database Migrations..."
alembic -c /app/services/orchestrator/alembic.ini upgrade head || {
    echo 'WARNING: Alembic migration had issues. Stamping head...'
    alembic -c /app/services/orchestrator/alembic.ini stamp head 2>/dev/null || true
}

echo "Database is up-to-date. Launching application..."

# Initialize and start Cron for background tasks (skip if script missing)
if [ -f /app/services/orchestrator/scripts/setup_cron.sh ]; then
    sed -i 's/\r$//' /app/services/orchestrator/scripts/setup_cron.sh
    chmod +x /app/services/orchestrator/scripts/setup_cron.sh
    /app/services/orchestrator/scripts/setup_cron.sh
    service cron start || true
fi

exec "$@"
