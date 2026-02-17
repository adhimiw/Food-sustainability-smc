"""
FoodFlow AI — CSV Exporter
Exports all database tables + analytics views to Kaggle-ready CSVs.

Usage:
    python data/export_csv.py                  # default seed=42
    python data/export_csv.py --seed 12345     # randomized dataset
    python data/export_csv.py --skip-reseed    # export existing DB as-is
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from database.db import get_db
from data.seed_database import seed_database

# ── Output directory ─────────────────────────────────────────
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kaggle_export")


def export_raw_tables(conn, out: str):
    """Dump every raw table to its own CSV."""
    raw_dir = os.path.join(out, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    tables = [
        "products", "stores", "suppliers", "supplier_products",
        "weather", "events", "sales", "inventory",
    ]
    summary = {}
    for t in tables:
        try:
            df = conn.execute(f"SELECT * FROM {t}").fetchdf()
            path = os.path.join(raw_dir, f"{t}.csv")
            df.to_csv(path, index=False)
            summary[t] = len(df)
            print(f"  ✅ {t}.csv — {len(df):,} rows")
        except Exception as e:
            print(f"  ⚠️  {t}: {e}")
    return summary


def export_analytics(conn, out: str):
    """Build useful analytics CSVs that look like real-world Kaggle datasets."""
    analytics_dir = os.path.join(out, "analytics")
    os.makedirs(analytics_dir, exist_ok=True)

    # ── 1. Daily Store Sales Summary ─────────────────────────
    df = conn.execute("""
        SELECT s.date, s.store_id, st.name AS store_name, st.city,
               COUNT(DISTINCT s.product_id)        AS unique_products_sold,
               ROUND(SUM(s.qty_ordered), 1)        AS total_ordered_kg,
               ROUND(SUM(s.qty_sold), 1)           AS total_sold_kg,
               ROUND(SUM(s.qty_wasted), 1)         AS total_wasted_kg,
               ROUND(SUM(s.revenue), 2)            AS revenue,
               ROUND(SUM(s.waste_cost), 2)         AS waste_cost,
               s.weather_temp                      AS temperature_c,
               MAX(s.event_flag)                    AS had_event,
               s.day_of_week, s.month
        FROM sales s
        JOIN stores st ON s.store_id = st.store_id
        WHERE st.store_type = 'retailer'
        GROUP BY s.date, s.store_id, st.name, st.city, s.weather_temp, s.day_of_week, s.month
        ORDER BY s.date, s.store_id
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "daily_store_sales.csv"), index=False)
    print(f"  ✅ daily_store_sales.csv — {len(df):,} rows")

    # ── 2. Product Waste Analysis ────────────────────────────
    df = conn.execute("""
        SELECT p.product_id, p.name AS product_name, p.category, p.subcategory,
               p.shelf_life_days, p.is_perishable,
               p.unit_cost, p.unit_price, p.carbon_footprint_kg,
               ROUND(SUM(s.qty_ordered), 1)        AS total_ordered_kg,
               ROUND(SUM(s.qty_sold), 1)           AS total_sold_kg,
               ROUND(SUM(s.qty_wasted), 1)         AS total_wasted_kg,
               ROUND(SUM(s.revenue), 2)            AS total_revenue,
               ROUND(SUM(s.waste_cost), 2)         AS total_waste_cost,
               ROUND(AVG(s.qty_wasted / NULLIF(s.qty_ordered, 0)) * 100, 2) AS avg_waste_rate_pct,
               COUNT(*)                            AS transaction_count
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        GROUP BY p.product_id, p.name, p.category, p.subcategory, p.shelf_life_days, p.is_perishable, p.unit_cost, p.unit_price, p.carbon_footprint_kg
        ORDER BY total_wasted_kg DESC
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "product_waste_analysis.csv"), index=False)
    print(f"  ✅ product_waste_analysis.csv — {len(df):,} rows")

    # ── 3. Weekly Category Trends ────────────────────────────
    df = conn.execute("""
        SELECT strftime(CAST(s.date AS DATE), '%Y-W%V') AS year_week,
               p.category,
               ROUND(SUM(s.qty_sold), 1)       AS sold_kg,
               ROUND(SUM(s.qty_wasted), 1)     AS wasted_kg,
               ROUND(SUM(s.revenue), 2)        AS revenue,
               ROUND(SUM(s.waste_cost), 2)     AS waste_cost,
               ROUND(AVG(s.weather_temp), 1)   AS avg_temp_c,
               COUNT(DISTINCT s.store_id)      AS store_count
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        GROUP BY year_week, p.category
        ORDER BY year_week, p.category
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "weekly_category_trends.csv"), index=False)
    print(f"  ✅ weekly_category_trends.csv — {len(df):,} rows")

    # ── 4. Store Performance Scorecard ───────────────────────
    df = conn.execute("""
        SELECT st.store_id, st.name AS store_name, st.city, st.store_type,
               st.capacity_kg, st.latitude, st.longitude,
               ROUND(SUM(s.qty_sold), 1)           AS total_sold_kg,
               ROUND(SUM(s.qty_wasted), 1)         AS total_wasted_kg,
               ROUND(SUM(s.revenue), 2)            AS total_revenue,
               ROUND(SUM(s.waste_cost), 2)         AS total_waste_cost,
               ROUND(SUM(s.qty_wasted) / NULLIF(SUM(s.qty_ordered), 0) * 100, 2) AS waste_rate_pct,
               COUNT(DISTINCT s.date)              AS active_days,
               COUNT(DISTINCT s.product_id)        AS products_stocked
        FROM stores st
        LEFT JOIN sales s ON st.store_id = s.store_id
        GROUP BY st.store_id, st.name, st.city, st.store_type, st.capacity_kg, st.latitude, st.longitude
        ORDER BY total_revenue DESC
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "store_performance.csv"), index=False)
    print(f"  ✅ store_performance.csv — {len(df):,} rows")

    # ── 5. Weather Impact on Sales ───────────────────────────
    df = conn.execute("""
        SELECT w.date, w.city, w.temp_c, w.humidity, w.precipitation_mm,
               w.wind_speed_kmh, w.condition,
               ROUND(SUM(s.qty_sold), 1)       AS total_sold_kg,
               ROUND(SUM(s.qty_wasted), 1)     AS total_wasted_kg,
               ROUND(SUM(s.revenue), 2)        AS revenue,
               COUNT(DISTINCT s.store_id)      AS stores_reporting
        FROM weather w
        LEFT JOIN stores st ON w.city = st.city AND st.store_type = 'retailer'
        LEFT JOIN sales s ON w.date = s.date AND s.store_id = st.store_id
        GROUP BY w.date, w.city, w.temp_c, w.humidity, w.precipitation_mm, w.wind_speed_kmh, w.condition
        ORDER BY w.date, w.city
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "weather_impact.csv"), index=False)
    print(f"  ✅ weather_impact.csv — {len(df):,} rows")

    # ── 6. Perishable Risk Matrix ────────────────────────────
    # ── 6. Perishable Risk Matrix ────────────────────────────
    df = conn.execute("""
        SELECT i.date, i.store_id, st.name AS store_name, st.city,
               i.product_id, p.name AS product_name, p.category,
               p.shelf_life_days, i.quantity_on_hand,
               i.days_until_expiry, i.freshness_score,
               ROUND(i.quantity_on_hand * p.unit_cost, 2) AS at_risk_cost,
               ROUND(i.quantity_on_hand * p.carbon_footprint_kg, 2) AS at_risk_co2_kg,
               CASE
                   WHEN i.days_until_expiry <= 1 THEN 'critical'
                   WHEN i.days_until_expiry <= 3 THEN 'high'
                   WHEN i.days_until_expiry <= 7 THEN 'medium'
                   ELSE 'low'
               END AS risk_level
        FROM inventory i
        JOIN products p ON i.product_id = p.product_id
        JOIN stores st ON i.store_id = st.store_id
        WHERE i.days_until_expiry <= 7
        ORDER BY i.days_until_expiry, at_risk_cost DESC
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "perishable_risk_matrix.csv"), index=False)
    print(f"  ✅ perishable_risk_matrix.csv — {len(df):,} rows")

    # ── 7. Monthly Waste by Category Pivot ───────────────────
    df = conn.execute("""
        SELECT SUBSTR(s.date, 1, 7) AS month,
               p.category,
               ROUND(SUM(s.qty_wasted), 1) AS wasted_kg,
               ROUND(SUM(s.waste_cost), 2) AS waste_cost,
               ROUND(SUM(s.qty_wasted) * p.carbon_footprint_kg, 1) AS co2_impact_kg
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        GROUP BY month, p.category, p.carbon_footprint_kg
        ORDER BY month, p.category
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "monthly_waste_by_category.csv"), index=False)
    print(f"  ✅ monthly_waste_by_category.csv — {len(df):,} rows")

    # ── 8. Event Impact Analysis ─────────────────────────────
    df = conn.execute("""
        SELECT e.date, e.event_name, e.event_type, e.city,
               e.impact_multiplier, e.affected_categories,
               ROUND(SUM(s.qty_sold), 1)       AS total_sold_kg,
               ROUND(SUM(s.qty_wasted), 1)     AS total_wasted_kg,
               ROUND(SUM(s.revenue), 2)        AS revenue,
               COUNT(DISTINCT s.product_id)    AS products_affected
        FROM events e
        LEFT JOIN stores st ON e.city = st.city AND st.store_type = 'retailer'
        LEFT JOIN sales s ON e.date = s.date AND s.store_id = st.store_id AND s.event_flag = 1
        GROUP BY e.event_id, e.date, e.event_name, e.event_type, e.city, e.impact_multiplier, e.affected_categories
        ORDER BY e.date
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "event_impact_analysis.csv"), index=False)
    print(f"  ✅ event_impact_analysis.csv — {len(df):,} rows")

    # ── 9. Carbon Footprint Summary ──────────────────────────
    df = conn.execute("""
        SELECT p.category,
               ROUND(SUM(s.qty_wasted), 1)                              AS total_wasted_kg,
               ROUND(SUM(s.qty_wasted) * p.carbon_footprint_kg, 1)      AS total_co2_kg,
               ROUND(AVG(p.carbon_footprint_kg), 2)                     AS avg_co2_per_kg,
               ROUND(SUM(s.waste_cost), 2)                              AS total_waste_cost,
               COUNT(DISTINCT p.product_id)                             AS product_count
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        GROUP BY p.category, p.carbon_footprint_kg
        ORDER BY total_co2_kg DESC
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "carbon_footprint_summary.csv"), index=False)
    print(f"  ✅ carbon_footprint_summary.csv — {len(df):,} rows")

    # ── 10. Demand Forecasting Features ──────────────────────
    df = conn.execute("""
        SELECT s.date, s.store_id, s.product_id,
               p.name AS product_name, p.category,
               st.name AS store_name, st.city,
               s.qty_sold, s.qty_ordered, s.qty_wasted,
               s.revenue, s.waste_cost,
               s.weather_temp AS temp_c, s.event_flag,
               s.day_of_week, s.month,
               p.shelf_life_days, p.avg_daily_demand,
               p.unit_price, p.unit_cost, p.is_perishable
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        JOIN stores st ON s.store_id = st.store_id
        WHERE st.store_type = 'retailer'
        ORDER BY s.date, s.store_id, s.product_id
    """).fetchdf()
    df.to_csv(os.path.join(analytics_dir, "demand_forecasting_features.csv"), index=False)
    print(f"  ✅ demand_forecasting_features.csv — {len(df):,} rows")


def write_kaggle_metadata(out: str, seed: int, raw_summary: dict):
    """Write dataset-metadata.json for Kaggle CLI upload."""
    import json
    meta = {
        "title": "FoodFlow AI — Food Waste Supply Chain Dataset",
        "id": "your-kaggle-username/foodflow-food-waste-supply-chain",
        "subtitle": "1-year synthetic food retail dataset for demand forecasting & waste reduction",
        "description": (
            "Realistic synthetic dataset simulating 1 year (2025) of food retail "
            "supply chain operations across 3 cities, 15 locations, 148 products, and 200K+ "
            "transactions. Includes weather, events, inventory expiry tracking, and CO₂ "
            "footprint data. Built for demand prediction, waste cascade optimization, and "
            "route planning ML tasks.\n\n"
            f"Generated with random seed: {seed}\n\n"
            "### Raw Tables\n"
            + "\n".join(f"- **{t}**: {n:,} rows" for t, n in raw_summary.items())
            + "\n\n### Analytics Views\n"
            "- daily_store_sales, product_waste_analysis, weekly_category_trends\n"
            "- store_performance, weather_impact, perishable_risk_matrix\n"
            "- monthly_waste_by_category, event_impact_analysis\n"
            "- carbon_footprint_summary, demand_forecasting_features"
        ),
        "isPrivate": False,
        "licenses": [{"name": "CC0-1.0"}],
        "keywords": [
            "food waste", "supply chain", "demand forecasting",
            "sustainability", "carbon footprint", "retail analytics",
            "time series", "inventory management"
        ],
        "resources": []
    }
    # Add every CSV as a resource
    for folder in ["raw", "analytics"]:
        folder_path = os.path.join(out, folder)
        if os.path.isdir(folder_path):
            for fname in sorted(os.listdir(folder_path)):
                if fname.endswith(".csv"):
                    meta["resources"].append({
                        "path": f"{folder}/{fname}",
                        "description": fname.replace(".csv", "").replace("_", " ").title()
                    })

    meta_path = os.path.join(out, "dataset-metadata.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  ✅ dataset-metadata.json written")


def main():
    parser = argparse.ArgumentParser(description="Export FoodFlow data to Kaggle-ready CSVs")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed. Omit to use a new random seed each run.")
    parser.add_argument("--skip-reseed", action="store_true",
                        help="Export existing database without re-seeding.")
    parser.add_argument("--out", type=str, default=OUT_DIR,
                        help=f"Output directory (default: {OUT_DIR})")
    args = parser.parse_args()

    out = args.out
    os.makedirs(out, exist_ok=True)

    # ── Optionally re-seed with a new random dataset ─────────
    if not args.skip_reseed:
        seed = args.seed if args.seed is not None else int.from_bytes(os.urandom(4), "big") % 100_000
        print(f"\n{'='*60}")
        print(f"  🎲 Re-seeding database with seed={seed}")
        print(f"{'='*60}\n")
        seed_database(seed=seed)
    else:
        seed = 42  # for metadata
        print("\n⏭️  Skipping re-seed, exporting existing database.\n")

    # ── Export ────────────────────────────────────────────────
    print(f"\n📁 Exporting CSVs to: {out}")
    print("-" * 50)

    with get_db() as conn:
        print("\n📦 Raw Tables:")
        raw_summary = export_raw_tables(conn, out)

        print("\n📊 Analytics Views:")
        export_analytics(conn, out)

    # ── Kaggle metadata ──────────────────────────────────────
    print("\n📝 Kaggle Metadata:")
    write_kaggle_metadata(out, seed, raw_summary)

    print(f"\n{'='*60}")
    print(f"  ✅ EXPORT COMPLETE!")
    print(f"  📁 All CSVs in: {os.path.abspath(out)}")
    print(f"{'='*60}")
    print(f"\n  To upload to Kaggle:")
    print(f"    1. Edit dataset-metadata.json → set your Kaggle username")
    print(f"    2. pip install kaggle")
    print(f"    3. kaggle datasets create -p {os.path.abspath(out)}")
    print()


if __name__ == "__main__":
    main()
