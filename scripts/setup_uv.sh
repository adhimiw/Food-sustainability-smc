#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/3] Creating/updating uv environment..."
uv sync

echo "[2/3] Installing project in editable mode (optional for scripts)..."
uv pip install -e . || true

echo "[3/3] Verifying core imports..."
uv run python - <<'PY'
import fastapi, streamlit, duckdb, xgboost, mistralai, fastmcp
print("Core dependencies OK")
PY

echo "✅ uv setup complete"
