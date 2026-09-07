#!/bin/sh
set -eu
BASE=${BASE:-http://localhost:8080}
URL=${URL:-$BASE/maps/temperature-2m/7/67/46.webp}
CONCURRENCY=${CONCURRENCY:-32}
REQUESTS=${REQUESTS:-2000}
if command -v hey >/dev/null 2>&1; then
  exec hey -n "$REQUESTS" -c "$CONCURRENCY" "$URL"
fi
if command -v ab >/dev/null 2>&1; then
  exec ab -n "$REQUESTS" -c "$CONCURRENCY" "$URL"
fi
echo "Install 'hey' or ApacheBench ('ab'), or set URL to a valid tile endpoint." >&2
exit 1
