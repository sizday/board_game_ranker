#!/bin/sh

set -e  # Выходим при любой ошибке, кроме тех, что явно обработаны

echo "=== Starting backend service ==="

echo "Step 1: Waiting for database to be ready..."
if ! python wait_for_db.py; then
  echo "ERROR: Failed to connect to database after 30 seconds"
  exit 1
fi

echo "Step 2: Checking and restoring tables if needed..."
python check_tables.py || {
  echo "Warning: Table check/restore had issues, but continuing..."
}

echo "Step 3: Running Alembic migrations..."
if ! alembic -c alembic.ini upgrade head; then
  echo "Warning: Migration failed or already applied, continuing..."
fi

echo "Step 4: Starting application..."
exec python wsgi.py

