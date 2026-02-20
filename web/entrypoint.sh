#!/bin/sh
# Entrypoint for web container
# Injects API_URL into HTML and starts the static file server

set -e

API_URL="${API_URL:-http://localhost:8000}"

echo "✓ API_URL set to: $API_URL"
echo "✓ Starting static file server on port 8080..."

exec python -m http.server 8080 --directory /app/web
