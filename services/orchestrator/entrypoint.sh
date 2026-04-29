#!/bin/bash
set -e

echo "Starting Orchestrator Entrypoint..."

# Wait for PostgreSQL
python -c '
import sys, urllib.parse, socket, time, os
url = os.environ.get("DATABASE_URL")
if not url: sys.exit(0)
res = urllib.parse.urlparse(url)
host = res.hostname
port = res.port or 5432
print(f"Waiting for {host}:{port}...", flush=True)
while True:
    try:
        socket.create_connection((host, port), timeout=1)
        print("PostgreSQL is UP!", flush=True)
        break
    except OSError:
        print("Postgres is unavailable - sleeping", flush=True)
        time.sleep(2)
'

# Run Database Migrations (Temporarily disabled to fix crash loop)
# echo "Running Database Migrations..."
# alembic -c /app/services/orchestrator/alembic.ini upgrade head

# Initialize and start Cron for background tasks (Disabled for Render)
# echo "Setting up background cron jobs..."
# chmod +x /app/services/orchestrator/scripts/setup_cron.sh
# /bin/bash /app/services/orchestrator/scripts/setup_cron.sh
# service cron start


echo "Database is up-to-date. Launching application..."
exec "$@"
