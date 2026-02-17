# 🌿 FoodFlow AI — Food Waste Reduction Platform

> **AI-powered demand prediction & distribution optimization to reduce food waste, cut costs, and save the planet.**

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Hackathon](https://img.shields.io/badge/Hackathon-2026-orange)

---

## 🎯 Problem

Nearly **10% of global greenhouse gas emissions** come from food production and disposal of uneaten food. Retailers overstock, supply chains are inefficient, and edible food ends up in landfills.

## 💡 Our Solution: Waste Cascade Optimization

Unlike traditional approaches that only predict demand, FoodFlow AI introduces a **3-Tier Waste Cascade** — surplus at any tier automatically becomes supply for the next:

```
┌─────────────────────────────────────────────────────┐
│  Tier 1: Retailer → Redistribute to nearby stores   │
│  Tier 2: Food Bank → Feed communities before expiry  │
│  Tier 3: Compost → Zero landfill, biogas production  │
└─────────────────────────────────────────────────────┘
```

Every decision is scored with a **Carbon Savings Index** for real-time impact measurement.

---

## 🏗️ Architecture

```
foodflow-ai/
├── data/
│   └── seed_database.py        # Synthetic data generator (100K+ records)
├── database/
│   └── db.py                   # SQLite schema & connection manager
├── models/
│   ├── demand_forecaster.py    # XGBoost demand prediction (30+ features)
│   ├── waste_cascade.py        # 3-tier surplus redistribution optimizer
│   ├── route_optimizer.py      # VRP solver (OR-Tools / greedy fallback)
│   └── carbon_calculator.py    # CO₂ impact scoring & equivalencies
├── api/
│   └── main.py                 # FastAPI REST backend (20+ endpoints)
├── dashboard/
│   └── app.py                  # Streamlit interactive dashboard (6 pages)
├── utils/
│   └── helpers.py              # Shared utilities & data loaders
├── requirements.txt
├── run.py                      # One-click launcher
└── README.md
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd foodflow-ai
pip install -r requirements.txt
```

### 2. One-Click Launch (Recommended)
```bash
python run.py
```
This will:
- Seed the database with 100K+ synthetic records
- Train the AI demand forecaster
- Run waste cascade optimization
- Launch the dashboard at `http://localhost:8501`
- Start the API at `http://localhost:8000/docs`

### 3. Manual Steps (Optional)
```bash
# Seed database only
python data/seed_database.py

# Launch dashboard only
streamlit run dashboard/app.py

# Launch API only
uvicorn api.main:app --reload
```

### 4. Kaggle CSV + DuckDB Pipeline
```bash
# Generate a fully randomized CSV bundle
python data/export_random_csv_bundle.py --seed 987654 --output-dir data/kaggle_bundle

# (Optional) Let script pick a random seed automatically
python data/export_random_csv_bundle.py --output-dir data/kaggle_bundle

# Load that CSV bundle into DuckDB
python data/load_csv_to_duckdb.py --csv-root data/kaggle_bundle --duckdb-path data/foodflow.duckdb --overwrite
```

Kaggle upload (CLI):
```bash
cd data/kaggle_bundle
# Edit dataset-metadata.json -> set your Kaggle username in "id"
kaggle datasets create -p .
```

---

## 📊 Features

### 🔮 Demand Prediction
- **XGBoost** model with 30+ engineered features
- Temporal features: day_of_week, month, cyclical encodings
- Lag features: 7/14/30-day lags, rolling statistics
- External signals: weather, events, holidays
- **MAPE < 15%** on test data
- 7-day forecasts with confidence intervals

### ♻️ Waste Cascade Optimizer
- Real-time surplus detection from inventory
- 3-tier redistribution: retailer → food bank → composting
- Priority scoring by urgency, shelf life, carbon footprint
- Sankey diagram visualization of food flow

### 🗺️ Route Optimization
- Vehicle Routing Problem (VRP) using OR-Tools
- Constraints: capacity, time windows, freshness
- Greedy nearest-neighbor fallback
- Interactive map with Folium

### 🌍 Carbon Impact Tracking
- Category-specific CO₂ factors (meat=27kg, vegetables=0.7kg per kg)
- Real-time equivalencies: trees, car-km, flights
- Progress tracking toward 30% reduction target

### 📈 Analytics Dashboard
- 6 interactive pages with 20+ visualizations
- Store leaderboard (waste efficiency ranking)
- Product & category drill-downs
- Time-series analysis (weekly, monthly patterns)

---

## 📦 Dataset

All data is synthetically generated but realistic:

| Dataset | Records | Key Features |
|---------|---------|--------------|
| Products | 150+ | name, category, shelf_life, CO₂ footprint |
| Stores | 15 | retailers, food banks, composting facilities |
| Suppliers | 20 | location, capacity, reliability |
| Weather | 4,300+ | 2 years × 3 cities, temperature, conditions |
| Events | 150+ | holidays, sports, local events with impact |
| Sales | 100K+ | quantity, waste, revenue, weather correlation |
| Inventory | 15K+ | current stock, freshness scores |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| ML | XGBoost, scikit-learn |
| Optimization | Google OR-Tools |
| API | FastAPI + Uvicorn |
| Dashboard | Streamlit |
| Database | SQLite |
| Visualization | Plotly, Folium, Altair |
| Maps | Folium + streamlit-folium |

---

## 📡 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/overview` | Platform-wide KPIs |
| `GET /api/forecast?store_id=1&product_id=1` | Demand forecast |
| `POST /api/forecast/train` | Train/retrain model |
| `GET /api/cascade/optimize` | Run waste cascade |
| `GET /api/routes/optimize` | Optimize delivery routes |
| `GET /api/carbon/summary` | Carbon impact metrics |
| `GET /api/analytics/waste-by-category` | Category breakdown |
| `GET /api/analytics/store-leaderboard` | Store ranking |

Full API docs: `http://localhost:8000/docs`

---

## 📈 Impact Goals

| Metric | Target |
|--------|--------|
| Food waste reduction | 30% fewer discarded perishables |
| Cost savings | 30% lower waste-related costs |
| Carbon footprint | Measurable CO₂ reduction |
| Zero landfill | 100% via cascade (redistribute → compost) |

---

## 🏆 What Makes This Unique

1. **Waste Cascade Model** — Not just prediction, but automated 3-tier redistribution
2. **Carbon Savings Index** — Every action measured in real CO₂ impact
3. **Full Pipeline** — From data to prediction to optimization to dashboard
4. **Realistic Synthetic Data** — 100K+ correlated records across 7 tables
5. **One-Click Deploy** — `python run.py` does everything

---

*Built with 💚 for Hackathon 2026 — Waste Less. Feed More. Save Earth.*
