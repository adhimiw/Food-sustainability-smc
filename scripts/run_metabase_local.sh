#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="foodflow-metabase"
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$BASE_DIR/.metabase-data"
PLUGINS_DIR="$BASE_DIR/metabase-plugins"
PROJECT_DATA_DIR="$BASE_DIR/data"

mkdir -p "$DATA_DIR" "$PLUGINS_DIR" "$PROJECT_DATA_DIR"

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

docker run -d \
  --name "$CONTAINER_NAME" \
  -p 3000:3000 \
  -e MB_JETTY_PORT=3000 \
  -v "$DATA_DIR":/metabase-data \
  -v "$PLUGINS_DIR":/plugins \
  -v "$PROJECT_DATA_DIR":/project-data:ro \
  metabase/metabase:latest

echo "Waiting for Metabase health endpoint..."
for i in {1..60}; do
  if curl -sf http://localhost:3000/api/health >/dev/null; then
    echo "✅ Metabase is up at http://localhost:3000"
    exit 0
  fi
  sleep 2
done

echo "❌ Metabase did not become healthy in time"
exit 1
