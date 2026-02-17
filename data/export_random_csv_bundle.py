"""
Export a fully randomized FoodFlow dataset bundle as CSV files.

What this script does:
1) Seeds the SQLite database with a configurable random seed.
2) Exports raw relational tables to CSV.
3) Exports analytics-friendly derived CSVs.
4) Writes Kaggle metadata template and a manifest.
"""

import argparse
import json
import os
import shutil
import duckdb
import sys
from datetime import datetime, timezone
from pathlib import Path
from random import SystemRandom

import pandas as pd

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.seed_database import seed_database
from database.db import DB_PATH


RAW_TABLES = [
    "products",
    "stores",
    "suppliers",
    "supplier_products",
    "weather",
    "events",
    "sales",
    "inventory",
]


DERIVED_QUERIES = {
    "sales_enriched": """
        SELECT
            s.sale_id,
            s.date,
            s.store_id,
            st.name AS store_name,
            st.store_type,
            st.city,
            s.product_id,
            p.name AS product_name,
            p.category,
            p.subcategory,
            p.is_perishable,
            p.shelf_life_days,
            s.qty_ordered,
            s.qty_sold,
            s.qty_wasted,
            s.revenue,
            s.waste_cost,
            s.weather_temp,
            s.event_flag,
            s.day_of_week,
            s.month
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        JOIN stores st ON s.store_id = st.store_id
        ORDER BY s.date, s.store_id, s.product_id
    """,
    "daily_store_metrics": """
        SELECT
            s.date,
            s.store_id,
            st.name AS store_name,
            st.city,
            SUM(s.qty_ordered) AS total_ordered_kg,
            SUM(s.qty_sold) AS total_sold_kg,
            SUM(s.qty_wasted) AS total_wasted_kg,
            SUM(s.revenue) AS total_revenue,
            SUM(s.waste_cost) AS total_waste_cost,
            ROUND(
                100.0 * SUM(s.qty_wasted) / NULLIF(SUM(s.qty_sold + s.qty_wasted), 0),
                2
            ) AS waste_rate_pct
        FROM sales s
        JOIN stores st ON s.store_id = st.store_id
        GROUP BY s.date, s.store_id, st.name, st.city
        ORDER BY s.date, s.store_id
    """,
    "daily_category_metrics": """
        SELECT
            s.date,
            p.category,
            SUM(s.qty_ordered) AS total_ordered_kg,
            SUM(s.qty_sold) AS total_sold_kg,
            SUM(s.qty_wasted) AS total_wasted_kg,
            SUM(s.revenue) AS total_revenue,
            SUM(s.waste_cost) AS total_waste_cost,
            ROUND(
                100.0 * SUM(s.qty_wasted) / NULLIF(SUM(s.qty_sold + s.qty_wasted), 0),
                2
            ) AS waste_rate_pct
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        GROUP BY s.date, p.category
        ORDER BY s.date, p.category
    """,
    "store_leaderboard": """
        SELECT
            s.store_id,
            st.name AS store_name,
            st.city,
            SUM(s.qty_sold) AS total_sold_kg,
            SUM(s.qty_wasted) AS total_wasted_kg,
            SUM(s.revenue) AS total_revenue,
            SUM(s.waste_cost) AS total_waste_cost,
            ROUND(
                100.0 * SUM(s.qty_wasted) / NULLIF(SUM(s.qty_sold + s.qty_wasted), 0),
                2
            ) AS waste_rate_pct
        FROM sales s
        JOIN stores st ON s.store_id = st.store_id
        GROUP BY s.store_id, st.name, st.city
        ORDER BY waste_rate_pct ASC, total_wasted_kg ASC
    """,
    "inventory_risk_latest": """
        WITH latest_day AS (
            SELECT MAX(date) AS max_date FROM inventory
        )
        SELECT
            i.date,
            i.store_id,
            st.name AS store_name,
            st.city,
            i.product_id,
            p.name AS product_name,
            p.category,
            i.quantity_on_hand,
            i.days_until_expiry,
            i.freshness_score
        FROM inventory i
        JOIN products p ON i.product_id = p.product_id
        JOIN stores st ON i.store_id = st.store_id
        WHERE i.date = (SELECT max_date FROM latest_day)
          AND (i.days_until_expiry <= 2 OR i.freshness_score < 0.35)
        ORDER BY i.days_until_expiry ASC, i.freshness_score ASC
    """,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate randomized CSV dataset bundle from FoodFlow."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed. If omitted, a random seed is generated.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join("data", "kaggle_bundle"),
        help="Output directory for CSV bundle (relative to project root by default).",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not delete an existing output directory before export.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip database seeding and export current database as-is.",
    )
    return parser.parse_args()


def resolve_output_dir(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = Path(PROJECT_ROOT) / path
    return path


def prepare_output_dir(output_dir: Path, keep_existing: bool):
    if output_dir.exists() and not keep_existing:
        shutil.rmtree(output_dir)
    (output_dir / "raw").mkdir(parents=True, exist_ok=True)
    (output_dir / "analytics").mkdir(parents=True, exist_ok=True)


def export_raw_tables(conn, output_dir: Path) -> dict:
    row_counts = {}
    for table in RAW_TABLES:
        df = conn.execute(f"SELECT * FROM {table}").fetchdf()
        df.to_csv(output_dir / "raw" / f"{table}.csv", index=False)
        row_counts[f"raw.{table}"] = int(len(df))
    return row_counts


def export_derived_tables(conn, output_dir: Path) -> dict:
    row_counts = {}
    for name, query in DERIVED_QUERIES.items():
        df = conn.execute(query).fetchdf()
        df.to_csv(output_dir / "analytics" / f"{name}.csv", index=False)
        row_counts[f"analytics.{name}"] = int(len(df))
    return row_counts


def write_kaggle_metadata(output_dir: Path, seed: int):
    metadata = {
        "title": f"FoodFlow AI Randomized Synthetic Dataset (Seed {seed})",
        "id": f"your-kaggle-username/foodflow-ai-randomized-seed-{seed}",
        "licenses": [{"name": "CC0-1.0"}],
    }
    with open(output_dir / "dataset-metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def write_dataset_card(output_dir: Path, seed: int):
    text = f"""# FoodFlow AI Randomized Synthetic Dataset

This dataset bundle is synthetically generated from the FoodFlow AI simulator.

- Seed: `{seed}`
- Generated at: `{datetime.now(timezone.utc).isoformat()}`
- Source DB: `{DB_PATH}`

## Folders

- `raw/`: normalized relational tables
- `analytics/`: joined and aggregated CSVs for dashboards

## Tables (raw)

- products
- stores
- suppliers
- supplier_products
- weather
- events
- sales
- inventory

## Kaggle CLI

```bash
kaggle datasets create -p .
```

If creating a new Kaggle dataset, update `dataset-metadata.json` first:

- set your Kaggle username in `id`
- optionally change `title`
"""
    with open(output_dir / "README_DATASET.md", "w", encoding="utf-8") as f:
        f.write(text)


def write_manifest(output_dir: Path, seed: int, row_counts: dict):
    manifest = {
        "seed": seed,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_path": DB_PATH,
        "row_counts": row_counts,
    }
    with open(output_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def main():
    args = parse_args()
    seed = args.seed if args.seed is not None else SystemRandom().randint(1, 2_147_483_647)
    output_dir = resolve_output_dir(args.output_dir)

    prepare_output_dir(output_dir, keep_existing=args.keep_existing)

    if args.skip_seed:
        print("Skipping seed step; exporting existing SQLite data.")
    else:
        print(f"Seeding database with random seed: {seed}")
        seed_database(seed=seed)

    conn = duckdb.connect(DB_PATH)
    try:
        raw_counts = export_raw_tables(conn, output_dir)
        derived_counts = export_derived_tables(conn, output_dir)
    finally:
        conn.close()

    all_counts = {}
    all_counts.update(raw_counts)
    all_counts.update(derived_counts)

    write_kaggle_metadata(output_dir, seed)
    write_dataset_card(output_dir, seed)
    write_manifest(output_dir, seed, all_counts)

    print("\nCSV bundle created:")
    print(f"  {output_dir}")
    print(f"  seed={seed}")
    for key in sorted(all_counts):
        print(f"  - {key}: {all_counts[key]:,} rows")


if __name__ == "__main__":
    main()
