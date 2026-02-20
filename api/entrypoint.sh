#!/bin/sh
# Entrypoint for API container
# Verifies .env is present before starting uvicorn

set -e

if [ ! -f /app/.env ]; then
    echo "ERROR: .env file not found in /app/"
    echo "Please ensure .env is mounted as a volume with TEAMS_CLIENT_ID and TEAMS_TENANT_ID"
    exit 1
fi

echo "✓ .env file present"
echo "✓ Starting FastAPI server..."

exec python -m uvicorn server:app --host 0.0.0.0 --port 8000
