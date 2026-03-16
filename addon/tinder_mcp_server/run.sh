#!/usr/bin/env bash
set -e

OPTIONS_FILE="/data/options.json"

# Read options from Home Assistant add-on config
LOG_LEVEL=$(jq -r '.log_level // "info"' "$OPTIONS_FILE")
PORT=$(jq -r '.port // 3000' "$OPTIONS_FILE")
CACHE_TTL=$(jq -r '.cache_ttl // 300' "$OPTIONS_FILE")
RATE_LIMIT_MAX=$(jq -r '.rate_limit_max // 100' "$OPTIONS_FILE")

# Generate a random TOKEN_SECRET if not already present
TOKEN_SECRET_FILE="/data/token_secret"
if [ ! -f "$TOKEN_SECRET_FILE" ]; then
    cat /proc/sys/kernel/random/uuid > "$TOKEN_SECRET_FILE"
fi
TOKEN_SECRET=$(cat "$TOKEN_SECRET_FILE")

# Write .env file consumed by the Node.js server
cat > /app/.env <<EOF
NODE_ENV=production
PORT=${PORT}

# Tinder API
TINDER_API_BASE_URL=https://api.gotinder.com
TINDER_IMAGES_URL=https://images-ssl.gotinder.com
TINDER_STATS_URL=https://etl.tindersparks.com
TINDER_API_TIMEOUT=30000
TINDER_API_MAX_RETRIES=3

# Cache
CACHE_TTL=${CACHE_TTL}
CACHE_CHECK_PERIOD=60

# Rate limiting
RATE_LIMIT_WINDOW_MS=60000
RATE_LIMIT_MAX_REQUESTS=${RATE_LIMIT_MAX}

# Security
TOKEN_SECRET=${TOKEN_SECRET}
TOKEN_EXPIRY=24h

# Logging
LOG_LEVEL=${LOG_LEVEL}
EOF

echo "[tinder-mcp] Starting server on port ${PORT} (log_level=${LOG_LEVEL})"
cd /app

# Run directly from TypeScript sources in transpile-only mode.
# This avoids upstream `tsc` build failures while remaining stable for runtime.
exec node -r ts-node/register/transpile-only src/index.ts
