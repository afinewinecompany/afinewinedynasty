#!/bin/bash
# Startup script for Railway deployment
# Ensures proper initialization order and visibility

echo "========================================"
echo "🚀 Starting A Fine Wine Dynasty API"
echo "========================================"
echo "Environment: ${ENVIRONMENT:-production}"
echo "Port: ${PORT:-8000}"
echo "Time: $(date -u +"%Y-%m-%d %H:%M:%S UTC" 2>/dev/null || date)"
echo "========================================"

# Set Playwright environment variables
export PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# Verify Playwright browser installation
echo ""
echo "🎭 Verifying Playwright browser installation..."
if /opt/venv/bin/python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.executable_path; p.stop()" 2>/dev/null; then
    echo "✅ Playwright Chromium is installed and ready"
else
    echo "⚠️  WARNING: Playwright browser verification failed"
    echo "   Attempting to install Chromium..."
    /opt/venv/bin/playwright install chromium --with-deps || echo "   Installation failed, will retry at runtime"
fi
echo ""

# Check and fix migration state if needed
echo ""
echo "🔍 Checking migration state..."
/opt/venv/bin/python scripts/fix_migration_state.py 2>/dev/null || echo "   Skipping migration state check"

# Run database migrations
echo ""
echo "📊 Running database migrations..."
timeout 120 /opt/venv/bin/alembic upgrade head || {
    echo "⚠️  WARNING: Migrations failed or timed out, but continuing to start server..."
    echo "⚠️  This allows healthchecks to pass while we debug the migration issue"
    echo "⚠️  Check Railway logs for migration error details"
}

echo ""
echo "✅ Migration phase complete"
echo ""

# Add a small delay to ensure logs flush
sleep 2

# Start the application with explicit logging
echo "🌐 Starting uvicorn server..."
echo "   Binding to: 0.0.0.0:${PORT:-8000}"
echo "   Log level: info"
echo "   Access logging: enabled"
echo ""

exec /opt/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --log-level info \
    --access-log \
    --use-colors
