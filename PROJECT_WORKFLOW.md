# FoodFlow AI Complete Project Workflow

This document maps the **full workflow** of the current codebase, from data generation to AI-powered dashboards and APIs.

Scope covered from code:
- `app.py`, `run.py`, `api/main.py`
- `pages/1_dashboard.py`, `pages/2_chatbot.py`, `pages/3_agentic.py`
- `models/*.py`, `utils/*.py`, `database/db.py`
- `data/*.py` export/load/seed pipeline
- Legacy standalone apps: `dashboard/app.py`, `chatbot/app.py`, `agentic/app.py`

---

## 1. High-Level Architecture

```mermaid
flowchart LR
    U[User] --> R[run.py]
    U --> A[app.py Streamlit Multi-Page]
    U --> API[FastAPI api/main.py]

    subgraph DATA[Data Layer]
      S[data/seed_database.py]
      D[(data/foodflow.duckdb)]
      P1[(data/foodflow_dashboard.duckdb)]
      P2[(data/foodflow_chatbot.duckdb)]
      P3[(data/foodflow_agentic.duckdb)]
      S --> D
      D --> P1
      D --> P2
      D --> P3
    end

    subgraph CORE[Core Logic]
      DF[models/demand_forecaster.py]
      WC[models/waste_cascade.py]
      RO[models/route_optimizer.py]
      CC[models/carbon_calculator.py]
      KB[utils/knowledge_base.py]
      H[utils/helpers.py]
    end

    subgraph UI[Streamlit Pages]
      PG1[pages/1_dashboard.py]
      PG2[pages/2_chatbot.py]
      PG3[pages/3_agentic.py]
    end

    subgraph EXT[External Services]
      M[Mistral API]
      MB[Metabase API localhost:3000]
      DOC[reports/*.docx output]
    end

    R --> S
    R --> DF
    R --> WC
    R --> RO
    R --> API
    R --> A

    A --> PG1
    A --> PG2
    A --> PG3

    PG1 --> H
    PG1 --> DF
    PG1 --> WC
    PG1 --> RO
    PG1 --> CC

    PG2 --> KB
    PG2 --> M

    PG3 --> KB
    PG3 --> M
    PG3 --> MB
    PG3 --> DOC

    API --> H
    API --> DF
    API --> WC
    API --> RO
    API --> CC

    H --> D
    DF --> D
    WC --> D
    RO --> D
    KB --> D
```

---

## 2. Boot & Runtime Sequence (`python run.py`)

```mermaid
sequenceDiagram
    actor User
    participant Run as run.py
    participant Seed as data/seed_database.py
    participant DB as data/foodflow.duckdb
    participant Forecast as models/demand_forecaster.py
    participant Cascade as models/waste_cascade.py
    participant Route as models/route_optimizer.py
    participant API as uvicorn api.main:app
    participant APP as streamlit app.py

    User->>Run: python run.py
    alt --skip-seed not used or DB missing
        Run->>Seed: seed_database()
        Seed->>DB: reset + init + insert products/stores/sales/inventory
    else --skip-seed with existing DB
        Run->>DB: use existing data
    end

    Run->>Forecast: train(days_back=365)
    Forecast->>DB: read sales/features

    Run->>Cascade: load_data() identify_surplus() optimize_cascade() save_actions()
    Cascade->>DB: read inventory/forecasts/stores
    Cascade->>DB: write waste_cascade_actions + carbon_impact

    Run->>Route: optimize_routes() save_routes()
    Route->>DB: read planned cascade actions
    Route->>DB: write routes

    Run->>API: start in background (port 8000)
    Run->>APP: start Streamlit app.py (port 8501)
```

---

## 3. Streamlit Multi-Page Workflow (`app.py`)

```mermaid
flowchart TD
    A0[app.py starts] --> A1[set_page_config]
    A1 --> A2[if main DB missing -> init_database]
    A2 --> A3[copy_db_for_page dashboard/chatbot/agentic]
    A3 --> A4[st.navigation]
    A4 --> A5[pages/1_dashboard.py]
    A4 --> A6[pages/2_chatbot.py]
    A4 --> A7[pages/3_agentic.py]
```

### Important DB behavior
- Each page calls `set_page_db("<page>")`.
- This creates/uses page-specific DuckDB copies (`foodflow_dashboard.duckdb`, etc.) to avoid locking.
- Main pipeline writes (from `run.py`) go to `foodflow.duckdb`.

---

## 4. Dashboard Page Workflow (`pages/1_dashboard.py`)

```mermaid
flowchart LR
    D0[set_page_db dashboard] --> D1[Sidebar page selector + date filters]
    D1 --> D2[Overview]
    D1 --> D3[Demand Forecast]
    D1 --> D4[Waste Cascade]
    D1 --> D5[Route Optimizer]
    D1 --> D6[Carbon Impact]
    D1 --> D7[Analytics]

    D2 --> Q1[query_df/get_waste_summary/get_daily_waste_trend]
    D3 --> M1[DemandForecaster train + predict]
    D4 --> M2[WasteCascadeOptimizer identify/optimize/save]
    D5 --> M3[RouteOptimizer optimize/save]
    D6 --> M4[carbon_calculator summary/equivalencies]
    D7 --> Q2[deep SQL analytics tabs]
```

---

## 5. Chatbot Workflow (`pages/2_chatbot.py`)

```mermaid
flowchart TD
    C0[set_page_db chatbot] --> C1[build_knowledge_text from utils/knowledge_base]
    C1 --> C2[User asks prebuilt or free-text question]
    C2 --> C3[Mistral chat.complete with tools]
    C3 --> C4{Tool call?}
    C4 -- query_database --> C5[run SQL via query_df]
    C4 -- get_themed_analysis --> C6[run_custom_query]
    C5 --> C7[Return tool output to Mistral]
    C6 --> C7
    C4 -- no --> C8[Direct response]
    C7 --> C8
    C8 --> C9[Render answer + optional Plotly chart]
```

Key elements:
- 20 prebuilt question templates with SQL + chart specs.
- Function-calling tools: `query_database`, `get_themed_analysis`.
- Knowledge context from `utils/knowledge_base.py`.

---

## 6. Agentic Workflow (`pages/3_agentic.py`)

Modes implemented:
1. Executive Summary
2. Deep-Dive Analysis
3. Client Report Generator
4. Live SQL Agent
5. Action Recommendations
6. Metabase Analytics (API/MCP-style actions)
7. Word Report Generator (markdown + existing docx integration)

```mermaid
flowchart TD
    G0[set_page_db agentic] --> G1[Load knowledge base + text]
    G1 --> G2[Select mode]
    G2 --> G3[Prompt Mistral with structured tasks]
    G3 --> G4[Optional SQL via query_df]
    G3 --> G5[Optional Metabase API calls]
    G3 --> G6[Optional report content JSON generation]
    G4 --> G7[Render dataframes/charts]
    G5 --> G7
    G6 --> G8[Generate downloadable markdown report]
```

---

## 7. API Workflow (`api/main.py`)

```mermaid
flowchart LR
    Client --> E0[/api/* endpoints]
    E0 --> E1[helpers + model modules]
    E1 --> DB[(foodflow.duckdb)]
    E1 --> JSON[JSON responses]
```

Endpoint groups:
- Overview: `/api/overview`, `/api/daily-waste-trend`
- Catalog: `/api/products`, `/api/stores`, categories
- Forecast: train, predict, metrics, surplus alerts
- Cascade: optimize, summary
- Routes: optimize, saved
- Carbon: summary, timeline
- Analytics: waste/category/store/top products/leaderboard
- Inventory + health checks

---

## 8. Data Engineering Pipeline

```mermaid
flowchart LR
    S[data/seed_database.py] --> DB[(foodflow.duckdb)]
    DB --> EX1[data/export_csv.py]
    DB --> EX2[data/export_random_csv_bundle.py]
    EX1 --> CSV1[data/kaggle_export/raw + analytics]
    EX2 --> CSV2[data/kaggle_bundle/raw + analytics + manifest]
    CSV1 --> LD1[data/load_duckdb.py]
    CSV2 --> LD2[data/load_csv_to_duckdb.py]
    LD1 --> D2[(data/foodflow.duckdb or target duckdb)]
    LD2 --> D3[(target duckdb with raw/analytics schemas)]
```

Outputs include:
- raw CSV tables
- analytics CSVs
- `dataset-metadata.json` for Kaggle
- optional DuckDB reload with schemas/views

---

## 9. Model-Specific Workflow

### Demand Forecasting
```mermaid
flowchart LR
    sales[Sales history] --> feat[Feature engineering]
    feat --> xgb[XGBoost]
    feat --> p[Prophet optional]
    xgb --> ens[Weighted ensemble]
    p --> ens
    ens --> pred[Forecasts + intervals]
    pred --> tbl[forecasts table]
```

### Waste Cascade + Routes
```mermaid
flowchart LR
    inv[Inventory + forecasts] --> surplus[Identify surplus]
    surplus --> t1[Tier1 retailer->retailer]
    surplus --> t2[Tier2 -> food bank]
    surplus --> t3[Tier3 -> compost]
    t1 --> actions[waste_cascade_actions]
    t2 --> actions
    t3 --> actions
    actions --> route[Route optimizer OR-Tools/greedy]
    route --> routes[routes table]
    actions --> carbon[carbon_impact table]
```

---

## 10. Practical Run Paths

### Full system
```bash
python run.py
```

### Unified UI only
```bash
streamlit run app.py --server.port 8501
```

### API only
```bash
uvicorn api.main:app --reload --port 8000
```

### Seed only
```bash
python data/seed_database.py
```

---

## 11. Notes on Current Structure

- `app.py` + `pages/*` is the active unified app path.
- `dashboard/app.py`, `chatbot/app.py`, `agentic/app.py` are legacy standalone entrypoints still present.
- Main orchestration and training/cascade/route priming happen in `run.py`.

