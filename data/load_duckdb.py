"""
FoodFlow AI — DuckDB Loader
Loads Kaggle-exported CSVs into DuckDB with raw + analytics schemas.

Usage:
    python data/load_duckdb.py                           # default paths
    python data/load_duckdb.py --csv-dir data/kaggle_export --db data/foodflow.duckdb
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import glob
import duckdb

DEFAULT_CSV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kaggle_export")
DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "foodflow.duckdb")


def load_csvs_to_duckdb(csv_dir: str, db_path: str):
    """Load all CSVs from raw/ and analytics/ into DuckDB schemas."""
    conn = duckdb.connect(db_path)

    print(f"\n🦆 DuckDB Loader")
    print(f"   CSV source : {os.path.abspath(csv_dir)}")
    print(f"   Database   : {os.path.abspath(db_path)}")
    print("=" * 60)

    # ── Create schemas ───────────────────────────────────────
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    conn.execute("CREATE SCHEMA IF NOT EXISTS analytics")

    total_tables = 0
    total_rows = 0

    for schema, folder in [("raw", "raw"), ("analytics", "analytics")]:
        csv_folder = os.path.join(csv_dir, folder)
        if not os.path.isdir(csv_folder):
            print(f"\n  ⚠️  Folder not found: {csv_folder}")
            continue

        csv_files = sorted(glob.glob(os.path.join(csv_folder, "*.csv")))
        if not csv_files:
            print(f"\n  ⚠️  No CSVs in {csv_folder}")
            continue

        print(f"\n📂 Schema: {schema} ({len(csv_files)} tables)")
        print("-" * 50)

        for csv_path in csv_files:
            table_name = os.path.splitext(os.path.basename(csv_path))[0]
            qualified = f"{schema}.{table_name}"

            # Drop if exists, then create from CSV
            conn.execute(f"DROP TABLE IF EXISTS {qualified}")
            conn.execute(f"""
                CREATE TABLE {qualified} AS
                SELECT * FROM read_csv_auto('{csv_path.replace(os.sep, '/')}',
                    header=true, sample_size=-1)
            """)

            row_count = conn.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0]
            col_count = len(conn.execute(f"SELECT * FROM {qualified} LIMIT 0").description)
            print(f"  ✅ {qualified:45s} {row_count:>10,} rows  ×  {col_count} cols")
            total_tables += 1
            total_rows += row_count

    # ── Create convenience views ─────────────────────────────
    print(f"\n📐 Creating views...")
    conn.execute("CREATE SCHEMA IF NOT EXISTS views")

    # Waste leaderboard
    conn.execute("""
        CREATE OR REPLACE VIEW views.waste_leaderboard AS
        SELECT product_name, category, total_wasted_kg,
               total_waste_cost, avg_waste_rate_pct,
               RANK() OVER (ORDER BY total_wasted_kg DESC) AS waste_rank
        FROM analytics.product_waste_analysis
        ORDER BY waste_rank
    """)
    print("  ✅ views.waste_leaderboard")

    # Store ranking
    conn.execute("""
        CREATE OR REPLACE VIEW views.store_ranking AS
        SELECT store_name, city, total_revenue,
               total_wasted_kg, waste_rate_pct,
               RANK() OVER (ORDER BY waste_rate_pct ASC) AS efficiency_rank
        FROM analytics.store_performance
        WHERE store_type = 'retailer'
        ORDER BY efficiency_rank
    """)
    print("  ✅ views.store_ranking")

    # High-risk inventory
    conn.execute("""
        CREATE OR REPLACE VIEW views.high_risk_inventory AS
        SELECT store_name, city, product_name, category,
               quantity_on_hand, days_until_expiry,
               at_risk_cost, at_risk_co2_kg, risk_level
        FROM analytics.perishable_risk_matrix
        WHERE risk_level IN ('critical', 'high')
        ORDER BY at_risk_cost DESC
    """)
    print("  ✅ views.high_risk_inventory")

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  🦆 DuckDB LOAD COMPLETE!")
    print(f"     Tables : {total_tables}")
    print(f"     Rows   : {total_rows:,}")
    print(f"     Views  : 3")
    print(f"     DB     : {os.path.abspath(db_path)}")
    print(f"{'='*60}")

    # ── Quick preview ────────────────────────────────────────
    print(f"\n🔍 Quick Preview — Top 5 wasted products:")
    result = conn.execute("""
        SELECT product_name, category,
               total_wasted_kg, total_waste_cost, avg_waste_rate_pct
        FROM analytics.product_waste_analysis
        ORDER BY total_wasted_kg DESC
        LIMIT 5
    """).fetchdf()
    print(result.to_string(index=False))

    print(f"\n🏪 Store Efficiency Ranking:")
    result = conn.execute("""
        SELECT store_name, city, total_revenue, waste_rate_pct
        FROM views.store_ranking
        LIMIT 5
    """).fetchdf()
    print(result.to_string(index=False))

    conn.close()
    print()


def main():
    parser = argparse.ArgumentParser(description="Load FoodFlow CSVs into DuckDB")
    parser.add_argument("--csv-dir", type=str, default=DEFAULT_CSV_DIR,
                        help=f"Path to kaggle_export folder (default: {DEFAULT_CSV_DIR})")
    parser.add_argument("--db", type=str, default=DEFAULT_DB,
                        help=f"DuckDB file path (default: {DEFAULT_DB})")
    args = parser.parse_args()
    load_csvs_to_duckdb(args.csv_dir, args.db)


if __name__ == "__main__":
    main()
