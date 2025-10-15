#!/bin/bash
set -e

echo "Starting application..."

# Run database migrations
echo "Running database migrations..."
/opt/venv/bin/alembic upgrade head

# Start the application
echo "Starting uvicorn server..."
exec /opt/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
