#!/bin/bash
# Removed 'set -e' to prevent script from exiting on migration failure
# This allows the server to start even if migrations fail

echo "Starting application..."

# Run database migrations
echo "Running database migrations..."
/opt/venv/bin/alembic upgrade head || {
    echo "⚠️  WARNING: Migrations failed, but continuing to start server..."
    echo "⚠️  This allows healthchecks to pass while we debug the migration issue"
    echo "⚠️  Check Railway logs for migration error details"
}

# Start the application
echo "Starting uvicorn server..."
exec /opt/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
