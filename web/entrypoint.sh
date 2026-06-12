#!/bin/sh
# Entrypoint for web container
# Copies web files, injects API_URL at runtime, and serves.
# This avoids modifying mounted source files.

set -e

API_URL="${API_URL:-http://localhost:8000}"
SERVE_DIR="/tmp/serve"

# Copy web files to a writable location
rm -rf "$SERVE_DIR"
cp -r /app/web "$SERVE_DIR"

# Inject API_BASE into the served copy
if ! grep -q 'window.API_BASE' "$SERVE_DIR/index.html" 2>/dev/null; then
  sed -i "s|</head>|<script>window.API_BASE = \"${API_URL}\";</script>\n</head>|" "$SERVE_DIR/index.html"
  echo "✓ Injected API_BASE = ${API_URL}"
fi

echo "✓ Starting static file server on port 8080..."

exec python -m http.server 8080 --directory "$SERVE_DIR"
