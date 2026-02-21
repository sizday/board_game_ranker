#!/bin/sh

set -e  # Выходим при любой ошибке, кроме тех, что явно обработаны

echo "=== Starting backend service ==="

echo "Step 1: Waiting for database to be ready..."
if ! (cd /app && python scripts/wait_for_db.py); then
  echo "ERROR: Failed to connect to database after 30 seconds"
  exit 1
fi

echo "Step 2: Creating/updating database tables..."
cd /app && python scripts/check_tables.py || {
  echo "Warning: Table creation had issues, but continuing..."
}

echo "Step 3: Starting application..."
exec python wsgi.py

