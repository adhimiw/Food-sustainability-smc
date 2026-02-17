#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# stdio MCP server for project context
uv run python mcp/project_context_server.py
