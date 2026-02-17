"""
FoodFlow AI — Knowledge Base Engine
Extracts comprehensive analytics from DuckDB and builds a structured
context document that the Mistral chatbot & agentic dashboard consume.

Every query is defensively written so missing tables / empty data never crash.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pandas as pd
import numpy as np
from datetime import datetime
from database.db import get_db, query_df, query_one, query_scalar


# ────────────────────────────────────────────────────────
#  Low-level data extractors (each returns a dict / list)
# ────────────────────────────────────────────────────────

def _safe_query_df(sql: str, params=None) -> pd.DataFrame:
    try:
        return query_df(sql, params)
    except Exception:
        return pd.DataFrame()


def _safe_scalar(sql: str, params=None):
    try:
        return query_scalar(sql, params)
    except Exception:
        return None


def get_platform_overview() -> dict:
    """High-level FoodFlow AI metrics."""
    total_sales = _safe_scalar("SELECT COUNT(*) FROM sales") or 0
    total_revenue = _safe_scalar("SELECT SUM(revenue) FROM sales") or 0
    total_waste_kg = _safe_scalar("SELECT SUM(qty_wasted) FROM sales") or 0
    total_waste_cost = _safe_scalar("SELECT SUM(waste_cost) FROM sales") or 0
    total_sold_kg = _safe_scalar("SELECT SUM(qty_sold) FROM sales") or 0
    num_products = _safe_scalar("SELECT COUNT(*) FROM products") or 0
    num_stores = _safe_scalar("SELECT COUNT(*) FROM stores") or 0
    num_suppliers = _safe_scalar("SELECT COUNT(*) FROM suppliers") or 0
    date_range_min = _safe_scalar("SELECT MIN(date) FROM sales") or "N/A"
    date_range_max = _safe_scalar("SELECT MAX(date) FROM sales") or "N/A"
    num_days = _safe_scalar("SELECT COUNT(DISTINCT date) FROM sales") or 1

    waste_rate = (total_waste_kg / (total_sold_kg + total_waste_kg) * 100) if (total_sold_kg + total_waste_kg) > 0 else 0
    avg_daily_revenue = total_revenue / num_days if num_days > 0 else 0
    avg_daily_waste = total_waste_kg / num_days if num_days > 0 else 0

    return {
        "total_transactions": int(total_sales),
        "date_range": f"{date_range_min} to {date_range_max}",
        "num_days": int(num_days),
        "num_products": int(num_products),
        "num_stores": int(num_stores),
        "num_suppliers": int(num_suppliers),
        "total_revenue": round(float(total_revenue), 2),
        "total_sold_kg": round(float(total_sold_kg), 2),
        "total_waste_kg": round(float(total_waste_kg), 2),
        "total_waste_cost": round(float(total_waste_cost), 2),
        "waste_rate_pct": round(waste_rate, 2),
        "avg_daily_revenue": round(avg_daily_revenue, 2),
        "avg_daily_waste_kg": round(avg_daily_waste, 2),
    }


def get_category_breakdown() -> list[dict]:
    """Waste and revenue breakdown by product category."""
    df = _safe_query_df("""
        SELECT p.category,
               COUNT(*) as transactions,
               SUM(s.qty_sold) as total_sold_kg,
               SUM(s.qty_wasted) as total_wasted_kg,
               SUM(s.revenue) as total_revenue,
               SUM(s.waste_cost) as total_waste_cost,
               AVG(s.qty_wasted / NULLIF(s.qty_ordered, 0)) * 100 as avg_waste_rate
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        GROUP BY p.category
        ORDER BY total_wasted_kg DESC
    """)
    if df.empty:
        return []
    return df.to_dict(orient="records")


def get_store_performance() -> list[dict]:
    """Per-store performance metrics."""
    df = _safe_query_df("""
        SELECT st.name as store_name, st.city, st.store_type,
               COUNT(*) as transactions,
               SUM(s.qty_sold) as total_sold_kg,
               SUM(s.qty_wasted) as total_wasted_kg,
               SUM(s.revenue) as total_revenue,
               SUM(s.waste_cost) as total_waste_cost,
               AVG(s.qty_wasted / NULLIF(s.qty_ordered, 0)) * 100 as avg_waste_rate
        FROM sales s
        JOIN stores st ON s.store_id = st.store_id
        GROUP BY st.name, st.city, st.store_type
        ORDER BY total_revenue DESC
    """)
    if df.empty:
        return []
    return df.to_dict(orient="records")


def get_monthly_trends() -> list[dict]:
    """Monthly aggregated trends."""
    df = _safe_query_df("""
        SELECT
            SUBSTR(date, 1, 7) as month,
            SUM(qty_sold) as sold_kg,
            SUM(qty_wasted) as wasted_kg,
            SUM(revenue) as revenue,
            SUM(waste_cost) as waste_cost,
            COUNT(DISTINCT store_id) as active_stores
        FROM sales
        GROUP BY SUBSTR(date, 1, 7)
        ORDER BY month
    """)
    if df.empty:
        return []
    df["waste_rate_pct"] = (df["wasted_kg"] / (df["sold_kg"] + df["wasted_kg"]) * 100).round(2)
    return df.to_dict(orient="records")


def get_top_wasted_products(n: int = 15) -> list[dict]:
    """Products with the highest absolute waste."""
    df = _safe_query_df(f"""
        SELECT p.name, p.category, p.shelf_life_days,
               SUM(s.qty_wasted) as total_wasted_kg,
               SUM(s.waste_cost) as total_waste_cost,
               AVG(s.qty_wasted / NULLIF(s.qty_ordered, 0)) * 100 as avg_waste_rate
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        GROUP BY p.name, p.category, p.shelf_life_days
        ORDER BY total_wasted_kg DESC
        LIMIT {n}
    """)
    if df.empty:
        return []
    return df.to_dict(orient="records")


def get_seasonality_insights() -> list[dict]:
    """Day-of-week and monthly patterns."""
    dow = _safe_query_df("""
        SELECT day_of_week,
               AVG(qty_sold) as avg_sold,
               AVG(qty_wasted) as avg_wasted,
               AVG(revenue) as avg_revenue
        FROM sales
        GROUP BY day_of_week
        ORDER BY day_of_week
    """)
    if dow.empty:
        return []
    day_names = {0: "Monday", 1: "Tuesday", 2: "Wednesday",
                 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
    dow["day_name"] = dow["day_of_week"].map(day_names)
    return dow.to_dict(orient="records")


def get_weather_impact() -> list[dict]:
    """How weather conditions correlate with sales and waste."""
    df = _safe_query_df("""
        SELECT w.condition,
               COUNT(*) as data_points,
               AVG(s.qty_sold) as avg_sold,
               AVG(s.qty_wasted) as avg_wasted,
               AVG(s.revenue) as avg_revenue
        FROM sales s
        JOIN weather w ON s.date = w.date
        GROUP BY w.condition
        HAVING COUNT(*) > 50
        ORDER BY avg_wasted DESC
    """)
    if df.empty:
        return []
    return df.to_dict(orient="records")


def get_cascade_summary() -> dict:
    """Waste cascade optimization summary."""
    total_actions = _safe_scalar("SELECT COUNT(*) FROM waste_cascade_actions") or 0
    if total_actions == 0:
        return {"total_actions": 0, "message": "No cascade actions have been run yet."}

    df = _safe_query_df("""
        SELECT cascade_tier,
               COUNT(*) as actions,
               SUM(quantity_kg) as total_kg,
               SUM(carbon_saved_kg) as carbon_saved,
               SUM(cost_saved) as cost_saved
        FROM waste_cascade_actions
        GROUP BY cascade_tier
        ORDER BY cascade_tier
    """)
    tier_names = {1: "Retailer-to-Retailer Redistribution",
                  2: "Food Bank Donation",
                  3: "Composting / Animal Feed",
                  4: "Energy Recovery",
                  5: "Landfill (last resort)"}
    tiers = []
    for _, row in df.iterrows():
        tiers.append({
            "tier": int(row["cascade_tier"]),
            "tier_name": tier_names.get(int(row["cascade_tier"]), f"Tier {int(row['cascade_tier'])}"),
            "actions": int(row["actions"]),
            "total_kg": round(float(row["total_kg"]), 1),
            "carbon_saved_kg": round(float(row["carbon_saved"]), 1),
            "cost_saved": round(float(row["cost_saved"]), 2),
        })
    total_carbon = _safe_scalar("SELECT SUM(carbon_saved_kg) FROM waste_cascade_actions") or 0
    total_cost = _safe_scalar("SELECT SUM(cost_saved) FROM waste_cascade_actions") or 0
    total_kg = _safe_scalar("SELECT SUM(quantity_kg) FROM waste_cascade_actions") or 0

    return {
        "total_actions": int(total_actions),
        "total_food_redirected_kg": round(float(total_kg), 1),
        "total_carbon_saved_kg": round(float(total_carbon), 1),
        "total_cost_saved": round(float(total_cost), 2),
        "tiers": tiers,
    }


def get_route_summary() -> dict:
    """Route optimization summary."""
    total_routes = _safe_scalar("SELECT COUNT(*) FROM routes") or 0
    if total_routes == 0:
        return {"total_routes": 0, "message": "No routes have been optimized yet."}
    return {
        "total_routes": int(total_routes),
        "total_distance_km": round(float(_safe_scalar("SELECT SUM(total_distance_km) FROM routes") or 0), 1),
        "total_time_minutes": round(float(_safe_scalar("SELECT SUM(total_time_minutes) FROM routes") or 0), 1),
        "total_load_kg": round(float(_safe_scalar("SELECT SUM(total_load_kg) FROM routes") or 0), 1),
        "total_carbon_emission_kg": round(float(_safe_scalar("SELECT SUM(carbon_emission_kg) FROM routes") or 0), 2),
    }


def get_carbon_summary() -> dict:
    """Carbon impact tracking."""
    total_saved = _safe_scalar("SELECT SUM(carbon_saved_kg) FROM waste_cascade_actions") or 0
    route_emissions = _safe_scalar("SELECT SUM(carbon_emission_kg) FROM routes") or 0
    net_carbon = float(total_saved) - float(route_emissions)

    # Category-level carbon data
    cat_df = _safe_query_df("""
        SELECT p.category,
               SUM(s.qty_wasted * p.carbon_footprint_kg / 100) as carbon_from_waste_kg,
               SUM(s.qty_wasted) as wasted_kg
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        GROUP BY p.category
        ORDER BY carbon_from_waste_kg DESC
    """)
    categories = cat_df.to_dict(orient="records") if not cat_df.empty else []

    return {
        "total_carbon_saved_kg": round(float(total_saved), 1),
        "route_emissions_kg": round(float(route_emissions), 2),
        "net_carbon_impact_kg": round(net_carbon, 1),
        "carbon_from_waste_by_category": categories,
    }


def get_forecast_performance() -> dict:
    """Demand forecasting model performance."""
    total_forecasts = _safe_scalar("SELECT COUNT(*) FROM forecasts") or 0
    if total_forecasts == 0:
        return {"total_forecasts": 0, "message": "No forecasts generated yet."}
    avg_confidence = _safe_scalar("SELECT AVG(confidence) FROM forecasts") or 0
    models_used = _safe_query_df("SELECT DISTINCT model_used FROM forecasts")
    model_list = models_used["model_used"].tolist() if not models_used.empty else []

    return {
        "total_forecasts": int(total_forecasts),
        "avg_confidence": round(float(avg_confidence), 1),
        "models_used": model_list,
    }


def get_inventory_health() -> dict:
    """Current inventory health snapshot."""
    latest_date = _safe_scalar("SELECT MAX(date) FROM inventory")
    if not latest_date:
        return {"message": "No inventory data available."}

    total_items = _safe_scalar(
        "SELECT COUNT(*) FROM inventory WHERE date = ?", [latest_date]) or 0
    critical = _safe_scalar(
        "SELECT COUNT(*) FROM inventory WHERE date = ? AND freshness_score < 0.3", [latest_date]) or 0
    expiring_soon = _safe_scalar(
        "SELECT COUNT(*) FROM inventory WHERE date = ? AND days_until_expiry <= 2", [latest_date]) or 0
    total_qty = _safe_scalar(
        "SELECT SUM(quantity_on_hand) FROM inventory WHERE date = ?", [latest_date]) or 0
    avg_freshness = _safe_scalar(
        "SELECT AVG(freshness_score) FROM inventory WHERE date = ?", [latest_date]) or 0

    return {
        "snapshot_date": str(latest_date),
        "total_items": int(total_items),
        "total_quantity_on_hand_kg": round(float(total_qty), 1),
        "avg_freshness_score": round(float(avg_freshness), 3),
        "critical_items": int(critical),
        "expiring_within_2_days": int(expiring_soon),
    }


def get_supplier_overview() -> list[dict]:
    """Supplier performance."""
    df = _safe_query_df("""
        SELECT s.name, s.city, s.lead_time_hours, s.reliability_score,
               s.capacity_kg_per_day,
               COUNT(sp.product_id) as products_supplied
        FROM suppliers s
        LEFT JOIN supplier_products sp ON s.supplier_id = sp.supplier_id
        GROUP BY s.name, s.city, s.lead_time_hours, s.reliability_score, s.capacity_kg_per_day
        ORDER BY s.reliability_score DESC
    """)
    if df.empty:
        return []
    return df.to_dict(orient="records")


# ────────────────────────────────────────────────────────
#  Composite knowledge base builder
# ────────────────────────────────────────────────────────

def build_knowledge_base() -> dict:
    """
    Build the full knowledge base dictionary.
    Every section is independently safe — partial failures
    do not prevent other sections from loading.
    """
    kb = {}
    sections = {
        "platform_overview": get_platform_overview,
        "category_breakdown": get_category_breakdown,
        "store_performance": get_store_performance,
        "monthly_trends": get_monthly_trends,
        "top_wasted_products": get_top_wasted_products,
        "seasonality": get_seasonality_insights,
        "weather_impact": get_weather_impact,
        "cascade_optimization": get_cascade_summary,
        "route_optimization": get_route_summary,
        "carbon_impact": get_carbon_summary,
        "forecast_performance": get_forecast_performance,
        "inventory_health": get_inventory_health,
        "suppliers": get_supplier_overview,
    }
    for name, fn in sections.items():
        try:
            kb[name] = fn()
        except Exception as e:
            kb[name] = {"error": str(e)}
    return kb


def build_knowledge_text() -> str:
    """
    Convert the knowledge base into a readable text document
    suitable for injecting into an LLM system prompt.
    """
    kb = build_knowledge_base()
    lines = []

    # ── Platform Overview ──
    ov = kb.get("platform_overview", {})
    lines.append("=== FOODFLOW AI — PLATFORM OVERVIEW ===")
    lines.append(f"Data Period: {ov.get('date_range', 'N/A')} ({ov.get('num_days', 0)} days)")
    lines.append(f"Stores: {ov.get('num_stores', 0)} | Products: {ov.get('num_products', 0)} | Suppliers: {ov.get('num_suppliers', 0)}")
    lines.append(f"Total Transactions: {ov.get('total_transactions', 0):,}")
    lines.append(f"Total Revenue: ${ov.get('total_revenue', 0):,.2f} (avg ${ov.get('avg_daily_revenue', 0):,.2f}/day)")
    lines.append(f"Total Sold: {ov.get('total_sold_kg', 0):,.0f} kg")
    lines.append(f"Total Waste: {ov.get('total_waste_kg', 0):,.0f} kg (${ov.get('total_waste_cost', 0):,.2f} cost)")
    lines.append(f"Waste Rate: {ov.get('waste_rate_pct', 0):.2f}%")
    lines.append(f"Avg Daily Waste: {ov.get('avg_daily_waste_kg', 0):,.0f} kg")
    lines.append("")

    # ── Category Breakdown ──
    cats = kb.get("category_breakdown", [])
    if cats:
        lines.append("=== WASTE BY PRODUCT CATEGORY ===")
        for c in cats:
            lines.append(f"  {c.get('category', '?')}: "
                         f"Wasted {c.get('total_wasted_kg', 0):,.0f} kg "
                         f"(${c.get('total_waste_cost', 0):,.0f}), "
                         f"Waste Rate {c.get('avg_waste_rate', 0):.1f}%, "
                         f"Revenue ${c.get('total_revenue', 0):,.0f}")
        lines.append("")

    # ── Store Performance ──
    stores = kb.get("store_performance", [])
    if stores:
        lines.append("=== STORE PERFORMANCE ===")
        for s in stores:
            lines.append(f"  {s.get('store_name', '?')} ({s.get('city', '?')}, {s.get('store_type', '?')}): "
                         f"Revenue ${s.get('total_revenue', 0):,.0f}, "
                         f"Waste {s.get('total_wasted_kg', 0):,.0f} kg "
                         f"({s.get('avg_waste_rate', 0):.1f}%)")
        lines.append("")

    # ── Monthly Trends ──
    trends = kb.get("monthly_trends", [])
    if trends:
        lines.append("=== MONTHLY TRENDS ===")
        for t in trends:
            lines.append(f"  {t.get('month', '?')}: "
                         f"Sold {t.get('sold_kg', 0):,.0f} kg, "
                         f"Wasted {t.get('wasted_kg', 0):,.0f} kg "
                         f"({t.get('waste_rate_pct', 0):.1f}%), "
                         f"Revenue ${t.get('revenue', 0):,.0f}")
        lines.append("")

    # ── Top Wasted Products ──
    twp = kb.get("top_wasted_products", [])
    if twp:
        lines.append("=== TOP 15 WASTED PRODUCTS ===")
        for i, p in enumerate(twp, 1):
            lines.append(f"  {i}. {p.get('name', '?')} ({p.get('category', '?')}, "
                         f"shelf life {p.get('shelf_life_days', '?')}d): "
                         f"{p.get('total_wasted_kg', 0):,.0f} kg wasted "
                         f"(${p.get('total_waste_cost', 0):,.0f})")
        lines.append("")

    # ── Seasonality ──
    seas = kb.get("seasonality", [])
    if seas:
        lines.append("=== DAY-OF-WEEK PATTERNS ===")
        for d in seas:
            lines.append(f"  {d.get('day_name', '?')}: "
                         f"Avg Sold {d.get('avg_sold', 0):.1f} kg, "
                         f"Avg Wasted {d.get('avg_wasted', 0):.1f} kg")
        lines.append("")

    # ── Weather Impact ──
    weather = kb.get("weather_impact", [])
    if weather:
        lines.append("=== WEATHER IMPACT ON SALES/WASTE ===")
        for w in weather:
            lines.append(f"  {w.get('condition', '?')} ({w.get('data_points', 0)} days): "
                         f"Avg Sold {w.get('avg_sold', 0):.1f} kg, "
                         f"Avg Wasted {w.get('avg_wasted', 0):.1f} kg")
        lines.append("")

    # ── Cascade Optimization ──
    casc = kb.get("cascade_optimization", {})
    if casc.get("total_actions", 0) > 0:
        lines.append("=== WASTE CASCADE OPTIMIZATION ===")
        lines.append(f"Total Actions: {casc['total_actions']}")
        lines.append(f"Food Redirected: {casc.get('total_food_redirected_kg', 0):,.1f} kg")
        lines.append(f"Carbon Saved: {casc.get('total_carbon_saved_kg', 0):,.1f} kg CO2")
        lines.append(f"Cost Saved: ${casc.get('total_cost_saved', 0):,.2f}")
        for t in casc.get("tiers", []):
            lines.append(f"  Tier {t['tier']} ({t['tier_name']}): "
                         f"{t['total_kg']:,.1f} kg, {t['actions']} actions, "
                         f"{t['carbon_saved_kg']:,.1f} kg CO2 saved")
        lines.append("")

    # ── Route Optimization ──
    routes = kb.get("route_optimization", {})
    if routes.get("total_routes", 0) > 0:
        lines.append("=== ROUTE OPTIMIZATION ===")
        lines.append(f"Routes Planned: {routes['total_routes']}")
        lines.append(f"Total Distance: {routes.get('total_distance_km', 0):.1f} km")
        lines.append(f"Total Time: {routes.get('total_time_minutes', 0):.0f} min")
        lines.append(f"Total Load: {routes.get('total_load_kg', 0):.1f} kg")
        lines.append(f"Route Emissions: {routes.get('total_carbon_emission_kg', 0):.2f} kg CO2")
        lines.append("")

    # ── Carbon Impact ──
    carbon = kb.get("carbon_impact", {})
    lines.append("=== CARBON IMPACT ===")
    lines.append(f"Total Carbon Saved (cascade): {carbon.get('total_carbon_saved_kg', 0):,.1f} kg CO2")
    lines.append(f"Route Emissions: {carbon.get('route_emissions_kg', 0):.2f} kg CO2")
    lines.append(f"Net Carbon Impact: {carbon.get('net_carbon_impact_kg', 0):,.1f} kg CO2 saved")
    carb_cats = carbon.get("carbon_from_waste_by_category", [])
    if carb_cats:
        lines.append("Carbon from waste by category:")
        for cc in carb_cats:
            lines.append(f"  {cc.get('category', '?')}: "
                         f"{cc.get('carbon_from_waste_kg', 0):,.1f} kg CO2 "
                         f"({cc.get('wasted_kg', 0):,.0f} kg wasted)")
    lines.append("")

    # ── Forecast Performance ──
    fc = kb.get("forecast_performance", {})
    lines.append("=== AI DEMAND FORECASTING ===")
    lines.append(f"Total Forecasts Generated: {fc.get('total_forecasts', 0):,}")
    lines.append(f"Avg Confidence: {fc.get('avg_confidence', 0):.1f}%")
    lines.append(f"Models Used: {', '.join(fc.get('models_used', []))}")
    lines.append("")

    # ── Inventory Health ──
    inv = kb.get("inventory_health", {})
    if "snapshot_date" in inv:
        lines.append("=== CURRENT INVENTORY HEALTH ===")
        lines.append(f"Snapshot Date: {inv['snapshot_date']}")
        lines.append(f"Total Items: {inv.get('total_items', 0):,}")
        lines.append(f"Total Quantity: {inv.get('total_quantity_on_hand_kg', 0):,.1f} kg")
        lines.append(f"Avg Freshness: {inv.get('avg_freshness_score', 0):.3f}")
        lines.append(f"Critical Items (freshness < 0.3): {inv.get('critical_items', 0)}")
        lines.append(f"Expiring within 2 days: {inv.get('expiring_within_2_days', 0)}")
        lines.append("")

    # ── Supplier Overview ──
    supps = kb.get("suppliers", [])
    if supps:
        lines.append("=== SUPPLIER OVERVIEW ===")
        for sp in supps:
            lines.append(f"  {sp.get('name', '?')} ({sp.get('city', '?')}): "
                         f"Reliability {sp.get('reliability_score', 0):.0%}, "
                         f"Lead Time {sp.get('lead_time_hours', 0):.0f}h, "
                         f"Capacity {sp.get('capacity_kg_per_day', 0):,.0f} kg/day, "
                         f"Products {sp.get('products_supplied', 0)}")
        lines.append("")

    # ── Platform Architecture & Methodology ──
    lines.append("=== PLATFORM ARCHITECTURE & METHODOLOGY ===")
    lines.append("")
    lines.append("## Technology Stack")
    lines.append("  - Language: Python 3.12")
    lines.append("  - Database: DuckDB (embedded OLAP, columnar storage, read-only concurrent access)")
    lines.append("  - Frontend: Streamlit multi-page app (unified on single port)")
    lines.append("  - AI/LLM: Mistral AI (mistral-small-latest) with function calling & tool use")
    lines.append("  - ML Models: XGBoost + Prophet ensemble for demand forecasting")
    lines.append("  - Optimization: Google OR-Tools (CVRP — Capacitated Vehicle Routing Problem)")
    lines.append("  - Visualization: Plotly (interactive charts), Folium (maps)")
    lines.append("  - BI: Metabase (via MCP — Model Context Protocol)")
    lines.append("  - Reporting: Word Document MCP Server (python-docx)")
    lines.append("  - API: FastAPI + Uvicorn (REST endpoints)")
    lines.append("")
    lines.append("## Database Schema (DuckDB)")
    lines.append("  Tables: products, stores, suppliers, supplier_products, weather, events,")
    lines.append("          sales, forecasts, waste_cascade_actions, routes, carbon_impact, inventory")
    lines.append("  - sales: Core transactional table with 365 days × 8 stores × many products")
    lines.append("  - products: 50+ products across 13 categories with carbon footprint data")
    lines.append("  - stores: 8 retailers + 3 food banks + 2 compost facilities + 1 warehouse")
    lines.append("  - Concurrent access via read_only=True connections for queries")
    lines.append("")
    lines.append("## AI & ML Methodology")
    lines.append("")
    lines.append("### Demand Forecasting (XGBoost + Prophet Ensemble)")
    lines.append("  - **XGBoost Gradient Boosted Trees**: Primary model (99.7% weight)")
    lines.append("    - 30+ engineered features: lag features (1,3,7,14,30 day), rolling means,")
    lines.append("      day-of-week, month, seasonality, weather temperature, event flags,")
    lines.append("      product shelf life, store capacity, historical avg demand")
    lines.append("    - Train/test split: 80/20 temporal split (no data leakage)")
    lines.append("    - Hyperparameters: max_depth=6, n_estimators=200, learning_rate=0.1")
    lines.append("  - **Prophet**: Secondary model (0.3% weight)")
    lines.append("    - Facebook/Meta time-series decomposition")
    lines.append("    - Captures trend, weekly/yearly seasonality, holiday effects")
    lines.append("  - **Ensemble**: Weighted average of both models, weights learned from validation MAE")
    lines.append("  - **Metrics**: MAE, MAPE, R² on held-out test set")
    lines.append("  - **Confidence intervals**: 95% prediction intervals from quantile regression")
    lines.append("")
    lines.append("### Waste Cascade Optimization (3-Tier)")
    lines.append("  - **Tier 1 — Retailer Redistribution**: Surplus from overstocked stores")
    lines.append("    → nearby stores with higher demand. Greedy nearest-neighbor matching.")
    lines.append("  - **Tier 2 — Food Bank Donation**: Remaining edible food → community food banks.")
    lines.append("    Distance-weighted allocation to minimize transport.")
    lines.append("  - **Tier 3 — Composting/Biogas**: Non-edible waste → composting facilities.")
    lines.append("    Zero-landfill target. Carbon credit tracking.")
    lines.append("  - Surplus identification: Compares inventory on-hand vs forecasted demand")
    lines.append("  - Carbon savings: Per-action CO₂ saved = quantity × category carbon factor")
    lines.append("")
    lines.append("### Route Optimization (OR-Tools CVRP)")
    lines.append("  - **Algorithm**: Google OR-Tools Capacitated Vehicle Routing Problem solver")
    lines.append("  - **Constraints**: Vehicle capacity (kg), time windows, depot location")
    lines.append("  - **Objective**: Minimize total distance while serving all pickup/delivery points")
    lines.append("  - **Distance matrix**: Haversine formula (great-circle distance)")
    lines.append("  - **Carbon tracking**: Distance × emission factor per vehicle type")
    lines.append("")
    lines.append("### Carbon Impact Calculation")
    lines.append("  - Per-category carbon emission factors (kg CO₂ per kg food):")
    lines.append("    Meat & Poultry: 13.0, Dairy & Eggs: 7.5, Seafood: 6.0,")
    lines.append("    Prepared Foods: 4.0, Beverages: 2.5, Bakery: 2.0, etc.")
    lines.append("  - Equivalencies: trees planted, car km avoided, flights saved,")
    lines.append("    homes powered, smartphones charged")
    lines.append("  - Net impact = cascade savings - route emissions")
    lines.append("")
    lines.append("### Chatbot & Agentic AI")
    lines.append("  - **Mistral AI** (mistral-small-latest) with function/tool calling")
    lines.append("  - **Knowledge Base**: 13 pre-computed data sections injected into system prompt")
    lines.append("  - **Tools**: query_database (live SQL), get_themed_analysis (pre-built queries)")
    lines.append("  - **20 Pre-built Questions**: Quick visualization with Plotly charts")
    lines.append("  - **Agentic Modes**: Executive Summary, Deep-Dive, Report Generator,")
    lines.append("    Live SQL Agent, Action Recommendations, Metabase Analytics, Word Reports")
    lines.append("")
    lines.append("## Integration & MCP")
    lines.append("  - **Metabase MCP**: Programmatic dashboard/card management via REST API")
    lines.append("    Docker container with DuckDB driver, 6 pre-built analytics cards")
    lines.append("  - **Word Document MCP**: Generate .docx reports with formatted tables,")
    lines.append("    alternating row colors, and professional styling")
    lines.append("  - **Unified Multi-Page App**: Single Streamlit process on one port")
    lines.append("    Dashboard, Chatbot, and Agentic pages — no DuckDB lock conflicts")
    lines.append("")

    return "\n".join(lines)


def run_custom_query(question: str) -> str:
    """
    Run a natural-language-inspired SQL query against the database.
    Used by the agentic dashboard to answer ad-hoc questions.
    Returns formatted results as a string.
    """
    # Map common question themes to SQL queries
    query_map = {
        "worst_stores": """
            SELECT st.name, st.city, SUM(s.qty_wasted) as waste_kg,
                   SUM(s.waste_cost) as waste_cost,
                   AVG(s.qty_wasted/NULLIF(s.qty_ordered,0))*100 as waste_rate
            FROM sales s JOIN stores st ON s.store_id = st.store_id
            GROUP BY st.name, st.city ORDER BY waste_kg DESC LIMIT 5
        """,
        "best_stores": """
            SELECT st.name, st.city, SUM(s.revenue) as revenue,
                   AVG(s.qty_wasted/NULLIF(s.qty_ordered,0))*100 as waste_rate
            FROM sales s JOIN stores st ON s.store_id = st.store_id
            GROUP BY st.name, st.city ORDER BY waste_rate ASC LIMIT 5
        """,
        "expiring_soon": """
            SELECT p.name, st.name as store, i.quantity_on_hand,
                   i.days_until_expiry, i.freshness_score
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            JOIN stores st ON i.store_id = st.store_id
            WHERE i.date = (SELECT MAX(date) FROM inventory)
              AND i.days_until_expiry <= 3
            ORDER BY i.days_until_expiry ASC LIMIT 20
        """,
        "high_demand": """
            SELECT p.name, p.category, AVG(f.predicted_demand) as avg_demand,
                   AVG(f.confidence) as avg_confidence
            FROM forecasts f
            JOIN products p ON f.product_id = p.product_id
            GROUP BY p.name, p.category
            ORDER BY avg_demand DESC LIMIT 10
        """,
        "recent_cascades": """
            SELECT wc.cascade_tier, p.name as product,
                   src.name as from_store, dst.name as to_store,
                   wc.quantity_kg, wc.carbon_saved_kg, wc.cost_saved
            FROM waste_cascade_actions wc
            JOIN products p ON wc.product_id = p.product_id
            JOIN stores src ON wc.source_store_id = src.store_id
            JOIN stores dst ON wc.destination_store_id = dst.store_id
            ORDER BY wc.action_id DESC LIMIT 15
        """,
    }

    # Try to match the question to a query
    q_lower = question.lower()
    if any(w in q_lower for w in ["worst", "most waste", "highest waste"]):
        key = "worst_stores"
    elif any(w in q_lower for w in ["best", "efficient", "lowest waste"]):
        key = "best_stores"
    elif any(w in q_lower for w in ["expir", "urgent", "critical"]):
        key = "expiring_soon"
    elif any(w in q_lower for w in ["demand", "forecast", "predict"]):
        key = "high_demand"
    elif any(w in q_lower for w in ["cascade", "redistrib", "action"]):
        key = "recent_cascades"
    else:
        return "I can provide information on: worst/best stores, expiring items, demand forecasts, and cascade actions."

    df = _safe_query_df(query_map[key])
    if df.empty:
        return "No data found for this query."
    return df.to_string(index=False)


# ────────────────────────────────────────────────────────
#  CLI test
# ────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(build_knowledge_text())
    print("\n\n--- Custom Query Test ---")
    print(run_custom_query("which stores have the most waste?"))
