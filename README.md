# 🌿 FoodFlow AI — Food Waste Reduction Platform

AI-powered demand prediction + redistribution optimization + agentic analytics to reduce waste, costs, and CO₂.

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![Database](https://img.shields.io/badge/DB-DuckDB-green)
![LLM](https://img.shields.io/badge/LLM-Mistral--Large--2512-orange)

---

## ✅ What is now configured

This repo is now set up to use:
- **Mistral model default:** `mistral-large-2512`
- **Local Metabase (Docker):** `http://localhost:3000`
- **Project-scoped MCP server:** `mcp/project_context_server.py`
- **uv-first workflow:** lockfile + virtual env + setup scripts

---

## 🧱 Architecture (current code)

- `app.py` → unified Streamlit multipage app
- `pages/1_dashboard.py` → analytics dashboard
- `pages/2_chatbot.py` → Mistral chatbot + tool calling + MCP hook
- `pages/3_agentic.py` → agentic analytics + Metabase integration
- `api/main.py` → FastAPI backend
- `database/db.py` → DuckDB schema and connection handling
- `utils/knowledge_base.py` → complete generated project knowledge context
- `mcp/project_context_server.py` → dedicated project MCP server (stdio)

---

## 🤖 Mistral setup (default: mistral-large-2512)

Environment variables:

```bash
export MISTRAL_API_KEY="your_key"
export MISTRAL_MODEL="mistral-large-2512"
```

Both chatbot and agentic pages now read these env vars (no hardcoded secrets).

---

## 🧠 Chatbot with complete knowledge base

`pages/2_chatbot.py` injects full project knowledge from `utils/knowledge_base.py`, including:
- KPIs and platform overview
- waste by category/store/product
- trends/seasonality/weather effects
- cascade + routing + carbon summaries
- inventory risk and supplier stats
- architecture/methodology context

It supports:
- 20 prebuilt analytics questions + charts
- live SQL tool (`query_database`)
- themed analysis tool (`get_themed_analysis`)
- **project MCP tool** (`query_project_mcp`)

---

## 🔌 MCP (project context server)

A dedicated MCP server exists for this project only:

- File: `mcp/project_context_server.py`
- Tools:
  - `get_knowledge_base_snapshot(max_chars)`
  - `query_project_context(question)`
  - `run_sql(sql, limit)` (read-only SELECT/WITH)

### Run MCP server directly
```bash
./scripts/run_project_mcp.sh
```

### Project mcporter config
Already added at:
- `config/mcporter.json` with server name `foodflow_project`

Example call:
```bash
mcporter call foodflow_project.get_knowledge_base_snapshot max_chars:400 --output json
```

---

## 📈 Metabase fully local (Docker)

### Start Metabase
```bash
./scripts/run_metabase_local.sh
```

or manual:
```bash
docker run -d \
  --name foodflow-metabase \
  -p 3000:3000 \
  -v $(pwd)/.metabase-data:/metabase-data \
  metabase/metabase:latest
```

Health check:
```bash
curl http://localhost:3000/api/health
```

Agentic Metabase mode uses env vars:
```bash
export METABASE_URL="http://localhost:3000"
export METABASE_DASHBOARD_ID="2"
export METABASE_USERNAME="your_admin_email"
export METABASE_PASSWORD="your_admin_password"
```

---

## ⚡ uv-first setup

### One-time setup
```bash
./scripts/setup_uv.sh
```

### Normal development
```bash
uv sync
uv run python run.py
```

### Run app/API manually
```bash
uv run streamlit run app.py --server.port 8501
uv run uvicorn api.main:app --reload --port 8000
```

---

## 📦 Requirements

- Python 3.12+
- uv
- Docker (for local Metabase)

Dependencies include:
- FastAPI, Streamlit, DuckDB
- XGBoost, OR-Tools, scikit-learn
- Mistral SDK (`mistralai`)
- FastMCP (`fastmcp`)

---

## 🔐 Security

Do not commit secrets. Use `.env` (see `.env.example`) or shell env vars for:
- `MISTRAL_API_KEY`
- `METABASE_USERNAME`
- `METABASE_PASSWORD`

---

Built for Hackathon 2026 — Waste Less. Feed More. Save Earth.
