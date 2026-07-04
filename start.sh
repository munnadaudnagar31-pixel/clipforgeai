#!/bin/bash
# Startup script for Docker container

echo "🚀 Starting ClipForge AI..."

# Ensure data directory exists for SQLite
mkdir -p /app/backend/data

# Run Alembic migrations (if any exist and are configured)
cd /app/backend
# If alembic.ini is present, run migrations. This is safe to run on every startup.
if [ -f "alembic.ini" ]; then
    echo "📦 Running database migrations..."
    # We ignore errors here in case it's a fresh DB without migrations set up properly yet,
    # as main.py has a lifespan event to create tables anyway.
    alembic upgrade head || true
fi

# Start FastAPI server via Uvicorn
echo "🌐 Starting web server on port 8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
