#!/bin/bash
set -e

echo "Starting MCGM PROPERTY LOOKUP Entrypoint..."

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

echo "Running Database Migrations..."
alembic -c /app/services/mcgm_property_lookup/alembic.ini upgrade head

echo "Database is up-to-date. Launching application..."
exec "$@"
