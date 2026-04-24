#!/bin/bash
set -e

echo "Starting RAG SERVICE Entrypoint..."

echo "Waiting for PostgreSQL at postgres:5432..."
until printf "" 2>>/dev/null >/dev/tcp/postgres/5432; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is UP!"

echo "Running Database Migrations..."
alembic upgrade head

echo "Database is up-to-date. Launching application..."
exec "$@"
