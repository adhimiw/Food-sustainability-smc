"""
FoodFlow Project Context MCP Server

Run (stdio mode):
    uv run python mcp/project_context_server.py

Exposes project-scoped tools for LLM agents:
- query_project_context(question)
- run_sql(sql, limit)
- get_knowledge_base_snapshot()
"""

import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp import FastMCP
from database.db import query_df
from utils.knowledge_base import build_knowledge_text, run_custom_query

mcp = FastMCP("foodflow-project-context")


@mcp.tool()
def get_knowledge_base_snapshot(max_chars: int = 8000) -> str:
    """Return a snapshot of the generated FoodFlow knowledge base text."""
    text = build_knowledge_text()
    if max_chars and max_chars > 0:
        return text[:max_chars]
    return text


@mcp.tool()
def query_project_context(question: str) -> str:
    """Answer project-specific questions using curated FoodFlow analytics mappings."""
    question = (question or "").strip()
    if not question:
        return "Please provide a question."
    return run_custom_query(question)


@mcp.tool()
def run_sql(sql: str, limit: int = 100) -> str:
    """
    Execute read-only SQL against the project DuckDB and return JSON rows.
    Safety: only allows SELECT / WITH queries.
    """
    sql = (sql or "").strip()
    if not sql:
        return json.dumps({"error": "SQL is required"})

    lowered = sql.lower().lstrip()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return json.dumps({"error": "Only SELECT/WITH read queries are allowed"})

    df = query_df(sql)
    if limit and limit > 0:
        df = df.head(limit)
    return df.to_json(orient="records")


if __name__ == "__main__":
    mcp.run()
