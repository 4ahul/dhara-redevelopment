#!/bin/bash
set -e

echo "Starting Orchestrator Entrypoint..."

# Wait for PostgreSQL
echo "Waiting for PostgreSQL at postgres:5432..."
until printf "" 2>>/dev/null >/dev/tcp/postgres/5432; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done
echo "PostgreSQL is UP!"

# Run Database Migrations (Temporarily disabled to fix crash loop)
# echo "Running Database Migrations..."
# alembic -c /app/services/orchestrator/alembic.ini upgrade head

# Initialize and start Cron for background tasks
echo "Setting up background cron jobs..."
chmod +x /app/services/orchestrator/scripts/setup_cron.sh
/bin/bash /app/services/orchestrator/scripts/setup_cron.sh
service cron start


echo "Database is up-to-date. Launching application..."
exec "$@"
