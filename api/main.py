"""
FoodFlow AI — FastAPI Backend
RESTful API serving demand forecasts, waste cascade, route optimization, and analytics.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import json
from datetime import datetime

from database.db import get_db, init_database
from utils.helpers import (
    get_sales_dataframe, get_products_dataframe, get_stores_dataframe,
    get_weather_dataframe, get_events_dataframe, get_inventory_dataframe,
    get_waste_summary, get_daily_waste_trend, format_currency, format_weight, format_co2
)
from models.carbon_calculator import (
    get_carbon_summary, get_equivalencies, calculate_food_saved_carbon
)

# ── App Setup ────────────────────────────────────────────────
app = FastAPI(
    title="FoodFlow AI",
    description="AI-Powered Food Waste Reduction Platform — Demand Prediction & Distribution Optimization",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
#  OVERVIEW / DASHBOARD ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/overview")
def get_overview():
    """Get platform-wide overview metrics."""
    try:
        waste = get_waste_summary()
        carbon = get_carbon_summary()

        total_waste_kg = waste.get("total_waste_kg", 0) or 0
        total_sold_kg = waste.get("total_sold_kg", 0) or 0
        total_revenue = waste.get("total_revenue", 0) or 0
        total_waste_cost = waste.get("total_waste_cost", 0) or 0
        waste_rate = (total_waste_kg / (total_sold_kg + total_waste_kg) * 100) if (total_sold_kg + total_waste_kg) > 0 else 0

        # Potential savings with AI (30% waste reduction target)
        potential_waste_reduction_kg = total_waste_kg * 0.30
        potential_cost_savings = total_waste_cost * 0.30
        potential_co2_savings = carbon.get("total_waste_co2_kg", 0) * 0.30

        equivalencies = get_equivalencies(potential_co2_savings)

        return {
            "current_metrics": {
                "total_sales_kg": round(total_sold_kg, 0),
                "total_waste_kg": round(total_waste_kg, 0),
                "waste_rate_pct": round(waste_rate, 1),
                "total_revenue": round(total_revenue, 2),
                "total_waste_cost": round(total_waste_cost, 2),
                "num_days": waste.get("num_days", 0),
                "num_stores": waste.get("num_stores", 0),
            },
            "ai_potential": {
                "waste_reduction_kg": round(potential_waste_reduction_kg, 0),
                "cost_savings": round(potential_cost_savings, 2),
                "co2_savings_kg": round(potential_co2_savings, 0),
                "equivalencies": equivalencies,
            },
            "carbon_summary": carbon,
            "cascade_savings_co2": carbon.get("cascade_savings_co2_kg", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/daily-waste-trend")
def daily_waste_trend(days: int = Query(90, ge=7, le=365)):
    """Get daily waste trend data for charts."""
    try:
        df = get_daily_waste_trend()
        df = df.tail(days)
        return {
            "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
            "total_waste": df["total_waste"].round(1).tolist(),
            "total_sold": df["total_sold"].round(1).tolist(),
            "waste_rate": df["waste_rate"].round(2).tolist(),
            "waste_cost": df["total_waste_cost"].round(2).tolist(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
#  PRODUCTS & STORES
# ═══════════════════════════════════════════════════════════════

@app.get("/api/products")
def list_products(category: Optional[str] = None):
    """List all products, optionally filtered by category."""
    df = get_products_dataframe()
    if category:
        df = df[df["category"] == category]
    return df.to_dict(orient="records")


@app.get("/api/products/categories")
def list_categories():
    """List all product categories."""
    df = get_products_dataframe()
    return sorted(df["category"].unique().tolist())


@app.get("/api/stores")
def list_stores(store_type: Optional[str] = None):
    """List all stores/locations."""
    df = get_stores_dataframe(store_type=store_type)
    return df.to_dict(orient="records")


# ═══════════════════════════════════════════════════════════════
#  DEMAND FORECASTING
# ═══════════════════════════════════════════════════════════════

@app.get("/api/forecast")
def get_forecast(store_id: int, product_id: int, days: int = Query(7, ge=1, le=30)):
    """Get demand forecast for a specific store-product combination."""
    try:
        from models.demand_forecaster import get_forecaster
        forecaster = get_forecaster()

        if not forecaster.is_trained:
            forecaster.train(days_back=365, verbose=False)

        preds = forecaster.predict(store_id, product_id, days_ahead=days, verbose=False)
        return {
            "store_id": store_id,
            "product_id": product_id,
            "days_ahead": days,
            "model_metrics": forecaster.metrics,
            "forecasts": preds.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/forecast/metrics")
def get_model_metrics():
    """Get current model training metrics."""
    try:
        from models.demand_forecaster import get_forecaster
        forecaster = get_forecaster()
        return {
            "is_trained": forecaster.is_trained,
            "metrics": forecaster.metrics,
            "feature_importance": getattr(forecaster, "feature_importance", {}),
            "training_info": forecaster.training_info,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/forecast/train")
def train_model(days_back: int = Query(365, ge=30)):
    """Train/retrain the demand forecasting model."""
    try:
        from models.demand_forecaster import get_forecaster
        forecaster = get_forecaster()
        metrics = forecaster.train(days_back=days_back, verbose=False)
        return {"status": "success", "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/forecast/surplus-alerts")
def get_surplus_alerts():
    """Get items with predicted surplus (candidates for redistribution)."""
    try:
        from models.demand_forecaster import get_forecaster
        forecaster = get_forecaster()
        if not forecaster.is_trained:
            forecaster.train(days_back=365, verbose=False)
        alerts = forecaster.get_surplus_alerts(days_ahead=3)
        if len(alerts) == 0:
            return {"alerts": [], "count": 0}
        return {
            "alerts": alerts.head(50).to_dict(orient="records"),
            "count": len(alerts),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
#  WASTE CASCADE
# ═══════════════════════════════════════════════════════════════

@app.get("/api/cascade/optimize")
def run_cascade_optimization():
    """Run waste cascade optimization."""
    try:
        from models.waste_cascade import get_cascade_optimizer
        optimizer = get_cascade_optimizer()
        optimizer.load_data()
        optimizer.identify_surplus(forecast_days=3)
        actions = optimizer.optimize_cascade()
        optimizer.save_actions()

        return {
            "summary": optimizer.summary,
            "actions": actions[:100],  # limit response size
            "sankey_data": optimizer.get_sankey_data(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cascade/summary")
def get_cascade_summary():
    """Get waste cascade summary from saved actions."""
    try:
        with get_db(read_only=True) as conn:
            tier_stats = conn.execute("""
                SELECT cascade_tier,
                       COUNT(*) as num_actions,
                       SUM(quantity_kg) as total_kg,
                       SUM(carbon_saved_kg) as carbon_saved,
                       SUM(cost_saved) as cost_saved
                FROM waste_cascade_actions
                GROUP BY cascade_tier
            """).fetchdf()

            recent_actions = conn.execute("""
                SELECT wca.*, p.name as product_name, p.category,
                       src.name as source_name, dst.name as dest_name
                FROM waste_cascade_actions wca
                JOIN products p ON wca.product_id = p.product_id
                JOIN stores src ON wca.source_store_id = src.store_id
                JOIN stores dst ON wca.destination_store_id = dst.store_id
                ORDER BY wca.created_at DESC
                LIMIT 50
            """).fetchdf()

        return {
            "tier_stats": tier_stats.to_dict(orient="records") if len(tier_stats) > 0 else [],
            "recent_actions": recent_actions.to_dict(orient="records") if len(recent_actions) > 0 else [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
#  ROUTE OPTIMIZATION
# ═══════════════════════════════════════════════════════════════

@app.get("/api/routes/optimize")
def optimize_routes(city: Optional[str] = None, vehicles: int = Query(3, ge=1, le=10)):
    """Optimize delivery routes."""
    try:
        from models.route_optimizer import get_route_optimizer
        optimizer = get_route_optimizer()
        routes = optimizer.optimize_routes(city=city, num_vehicles=vehicles)
        optimizer.save_routes()
        return {
            "summary": optimizer.summary,
            "routes": routes,
            "map_data": optimizer.get_route_map_data(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/routes/saved")
def get_saved_routes():
    """Get previously saved routes."""
    try:
        with get_db(read_only=True) as conn:
            routes = conn.execute("""
                SELECT * FROM routes ORDER BY created_at DESC LIMIT 20
            """).fetchdf()
        records = routes.to_dict(orient="records")
        for r in records:
            if r.get("stops_json"):
                r["stops"] = json.loads(r["stops_json"])
        return {"routes": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
#  CARBON IMPACT
# ═══════════════════════════════════════════════════════════════

@app.get("/api/carbon/summary")
def carbon_summary():
    """Get carbon impact summary."""
    try:
        summary = get_carbon_summary()
        total_co2 = summary.get("total_waste_co2_kg", 0)
        summary["equivalencies"] = get_equivalencies(total_co2 * 0.3)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/carbon/timeline")
def carbon_timeline():
    """Get carbon impact over time."""
    try:
        with get_db(read_only=True) as conn:
            df = conn.execute("""
                SELECT date,
                       SUM(food_saved_kg) as food_saved,
                       SUM(carbon_saved_kg) as carbon_saved,
                       SUM(cost_saved) as cost_saved
                FROM carbon_impact
                GROUP BY date
                ORDER BY date
            """).fetchdf()
        if len(df) == 0:
            return {"dates": [], "carbon_saved": [], "food_saved": []}
        return {
            "dates": df["date"].tolist(),
            "carbon_saved": df["carbon_saved"].round(1).tolist(),
            "food_saved": df["food_saved"].round(1).tolist(),
            "cost_saved": df["cost_saved"].round(2).tolist(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
#  ANALYTICS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/analytics/waste-by-category")
def waste_by_category():
    """Get waste breakdown by product category."""
    try:
        with get_db(read_only=True) as conn:
            df = conn.execute("""
                SELECT p.category,
                       SUM(s.qty_wasted) as total_waste_kg,
                       SUM(s.waste_cost) as total_waste_cost,
                       SUM(s.qty_sold) as total_sold_kg,
                       AVG(s.qty_wasted / NULLIF(s.qty_ordered, 0)) * 100 as avg_waste_rate
                FROM sales s
                JOIN products p ON s.product_id = p.product_id
                GROUP BY p.category
                ORDER BY total_waste_kg DESC
            """).fetchdf()
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/waste-by-store")
def waste_by_store():
    """Get waste breakdown by store."""
    try:
        with get_db(read_only=True) as conn:
            df = conn.execute("""
                SELECT st.name as store_name, st.city, st.store_type,
                       SUM(s.qty_wasted) as total_waste_kg,
                       SUM(s.waste_cost) as total_waste_cost,
                       SUM(s.qty_sold) as total_sold_kg,
                       AVG(s.qty_wasted / NULLIF(s.qty_ordered, 0)) * 100 as avg_waste_rate
                FROM sales s
                JOIN stores st ON s.store_id = st.store_id
                GROUP BY st.store_id
                ORDER BY total_waste_kg DESC
            """).fetchdf()
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/top-wasted-products")
def top_wasted_products(limit: int = Query(20, ge=5, le=100)):
    """Get top most wasted products."""
    try:
        with get_db(read_only=True) as conn:
            df = conn.execute(f"""
                SELECT p.name, p.category, p.shelf_life_days,
                       p.carbon_footprint_kg,
                       SUM(s.qty_wasted) as total_waste_kg,
                       SUM(s.waste_cost) as total_waste_cost,
                       AVG(s.qty_wasted / NULLIF(s.qty_ordered, 0)) * 100 as avg_waste_rate
                FROM sales s
                JOIN products p ON s.product_id = p.product_id
                GROUP BY p.product_id
                ORDER BY total_waste_kg DESC
                LIMIT {limit}
            """).fetchdf()
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/store-leaderboard")
def store_leaderboard():
    """Store performance leaderboard — lowest waste rate wins."""
    try:
        with get_db(read_only=True) as conn:
            df = conn.execute("""
                SELECT st.store_id, st.name as store_name, st.city,
                       SUM(s.qty_sold) as total_sold,
                       SUM(s.qty_wasted) as total_wasted,
                       SUM(s.revenue) as total_revenue,
                       SUM(s.waste_cost) as total_waste_cost,
                       ROUND(SUM(s.qty_wasted) * 100.0 / NULLIF(SUM(s.qty_ordered), 0), 2) as waste_rate_pct
                FROM sales s
                JOIN stores st ON s.store_id = st.store_id
                WHERE st.store_type = 'retailer'
                GROUP BY st.store_id
                ORDER BY waste_rate_pct ASC
            """).fetchdf()
        df["rank"] = range(1, len(df) + 1)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/inventory/critical")
def critical_inventory():
    """Get inventory items expiring soon or with low freshness."""
    try:
        df = get_inventory_dataframe(critical_only=True)
        if len(df) == 0:
            return {"items": [], "count": 0}
        df = df.sort_values("freshness_score").head(50)
        return {
            "items": df.to_dict(orient="records"),
            "count": len(df),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
#  HEALTH
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health")
def health_check():
    """API health check."""
    try:
        with get_db(read_only=True) as conn:
            count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        return {
            "status": "healthy",
            "database": "connected",
            "sales_records": count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    init_database()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
