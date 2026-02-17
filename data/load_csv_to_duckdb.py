"""
Load FoodFlow CSV bundle into DuckDB.

Expected input bundle layout:
- <bundle>/raw/*.csv
- <bundle>/analytics/*.csv
"""

import argparse
import os
import re
import sys
from pathlib import Path

import duckdb

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load FoodFlow CSV bundle into DuckDB.")
    parser.add_argument(
        "--csv-root",
        default=os.path.join("data", "kaggle_bundle"),
        help="Root folder containing raw/ and analytics/ CSV files.",
    )
    parser.add_argument(
        "--duckdb-path",
        default=os.path.join("data", "foodflow.duckdb"),
        help="DuckDB file path.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete existing DuckDB file first.",
    )
    return parser.parse_args()


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = Path(PROJECT_ROOT) / path
    return path


def sanitize_table_name(file_name: str) -> str:
    stem = Path(file_name).stem.lower()
    return re.sub(r"[^a-z0-9_]", "_", stem)


def load_schema(conn: duckdb.DuckDBPyConnection, schema: str, folder: Path) -> dict:
    counts = {}
    if not folder.exists():
        return counts

    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    csv_files = sorted(folder.glob("*.csv"))
    for csv_path in csv_files:
        table_name = sanitize_table_name(csv_path.name)
        fq_table = f"{schema}.{table_name}"
        conn.execute(
            f"""
            CREATE OR REPLACE TABLE {fq_table} AS
            SELECT * FROM read_csv_auto(?, HEADER=TRUE, SAMPLE_SIZE=-1)
            """,
            [str(csv_path)],
        )
        row_count = conn.execute(f"SELECT COUNT(*) FROM {fq_table}").fetchone()[0]
        counts[fq_table] = int(row_count)
    return counts


def create_useful_views(conn: duckdb.DuckDBPyConnection):
    conn.execute(
        """
        CREATE OR REPLACE VIEW analytics.kpi_overview AS
        SELECT
            COUNT(DISTINCT store_id) AS num_stores,
            COUNT(DISTINCT product_id) AS num_products,
            SUM(qty_sold) AS total_sold_kg,
            SUM(qty_wasted) AS total_wasted_kg,
            SUM(revenue) AS total_revenue,
            SUM(waste_cost) AS total_waste_cost,
            ROUND(100.0 * SUM(qty_wasted) / NULLIF(SUM(qty_sold + qty_wasted), 0), 2) AS waste_rate_pct
        FROM raw.sales
        """
    )


def main():
    args = parse_args()
    csv_root = resolve_path(args.csv_root)
    duckdb_path = resolve_path(args.duckdb_path)

    if args.overwrite and duckdb_path.exists():
        duckdb_path.unlink()

    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path))

    try:
        raw_counts = load_schema(conn, "raw", csv_root / "raw")
        analytics_counts = load_schema(conn, "analytics", csv_root / "analytics")
        create_useful_views(conn)
    finally:
        conn.close()

    all_counts = {}
    all_counts.update(raw_counts)
    all_counts.update(analytics_counts)

    print(f"DuckDB loaded: {duckdb_path}")
    for key in sorted(all_counts):
        print(f"  - {key}: {all_counts[key]:,} rows")
    print("  - analytics.kpi_overview: view created")


if __name__ == "__main__":
    main()
