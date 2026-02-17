"""
FoodFlow AI — Database Schema & Connection Manager
DuckDB-based persistent storage for all platform data.

Each Streamlit page gets its own DB copy to eliminate DuckDB file-locking.
Call set_page_db("dashboard") at the top of each page.
The main DB_PATH is only used for init/seed (write operations).
"""

import duckdb
import os
import shutil
import threading
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "foodflow.duckdb")
_DATA_DIR = os.path.dirname(DB_PATH)

# Thread-local storage for per-page DB path
_local = threading.local()


def copy_db_for_page(page_name: str) -> str:
    """Copy the main DB to a page-specific file. Returns the path."""
    dst = os.path.join(_DATA_DIR, f"foodflow_{page_name}.duckdb")
    # Remove stale WAL/TMP files for the copy
    for ext in [".wal", ".tmp"]:
        stale = dst + ext
        if os.path.exists(stale):
            os.remove(stale)
    shutil.copy2(DB_PATH, dst)
    return dst


def set_page_db(page_name: str):
    """Set the active DB for this thread to a page-specific copy."""
    _local.db_path = copy_db_for_page(page_name)


def _active_db():
    """Return the active DB path (page-specific if set, else main)."""
    return getattr(_local, "db_path", DB_PATH)


def get_connection(read_only: bool = False):
    """Get a new DuckDB connection to the active DB."""
    conn = duckdb.connect(_active_db(), read_only=read_only)
    return conn


@contextmanager
def get_db(read_only: bool = False):
    """Context manager for database connections."""
    conn = get_connection(read_only=read_only)
    try:
        yield conn
    except Exception:
        raise
    finally:
        conn.close()


def query_df(sql: str, params=None):
    """Run a read-only query and return a pandas DataFrame."""
    import pandas as pd
    with get_db(read_only=True) as conn:
        if params:
            return conn.execute(sql, params).fetchdf()
        return conn.execute(sql).fetchdf()


def query_one(sql: str, params=None) -> dict:
    """Run a read-only query and return the first row as a dict."""
    with get_db(read_only=True) as conn:
        if params:
            result = conn.execute(sql, params).fetchdf()
        else:
            result = conn.execute(sql).fetchdf()
        if len(result) == 0:
            return {}
        return result.iloc[0].to_dict()


def query_scalar(sql: str, params=None):
    """Run a read-only query and return a single scalar value."""
    with get_db(read_only=True) as conn:
        if params:
            row = conn.execute(sql, params).fetchone()
        else:
            row = conn.execute(sql).fetchone()
        return row[0] if row else None


def init_database():
    """Create all tables if they don't exist."""
    conn = duckdb.connect(DB_PATH)

    # ── Sequences ────────────────────────────────────────
    for seq in ["products", "stores", "suppliers", "weather", "events",
                "sales", "forecasts", "cascade", "routes", "carbon", "inventory"]:
        conn.execute(f"CREATE SEQUENCE IF NOT EXISTS seq_{seq} START 1")

    # ── Products ─────────────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER DEFAULT nextval('seq_products') PRIMARY KEY,
        name VARCHAR NOT NULL,
        category VARCHAR NOT NULL,
        subcategory VARCHAR,
        shelf_life_days INTEGER NOT NULL,
        avg_daily_demand DOUBLE NOT NULL,
        unit_cost DOUBLE NOT NULL,
        unit_price DOUBLE NOT NULL,
        carbon_footprint_kg DOUBLE NOT NULL,
        storage_temp_min DOUBLE,
        storage_temp_max DOUBLE,
        is_perishable INTEGER DEFAULT 1
    )""")

    # ── Stores / Hubs ────────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        store_id INTEGER DEFAULT nextval('seq_stores') PRIMARY KEY,
        name VARCHAR NOT NULL,
        store_type VARCHAR NOT NULL,
        latitude DOUBLE NOT NULL,
        longitude DOUBLE NOT NULL,
        capacity_kg DOUBLE NOT NULL,
        operating_hours_start INTEGER DEFAULT 8,
        operating_hours_end INTEGER DEFAULT 22,
        city VARCHAR,
        address VARCHAR
    )""")

    # ── Suppliers ────────────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id INTEGER DEFAULT nextval('seq_suppliers') PRIMARY KEY,
        name VARCHAR NOT NULL,
        latitude DOUBLE NOT NULL,
        longitude DOUBLE NOT NULL,
        lead_time_hours DOUBLE NOT NULL,
        reliability_score DOUBLE DEFAULT 0.9,
        capacity_kg_per_day DOUBLE NOT NULL,
        city VARCHAR
    )""")

    # ── Supplier-Product Mapping ─────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS supplier_products (
        supplier_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        unit_cost DOUBLE NOT NULL,
        min_order_qty DOUBLE DEFAULT 0,
        PRIMARY KEY (supplier_id, product_id)
    )""")

    # ── Weather Data ─────────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS weather (
        id INTEGER DEFAULT nextval('seq_weather') PRIMARY KEY,
        date VARCHAR NOT NULL,
        city VARCHAR NOT NULL,
        temp_c DOUBLE NOT NULL,
        humidity DOUBLE,
        precipitation_mm DOUBLE,
        wind_speed_kmh DOUBLE,
        condition VARCHAR,
        UNIQUE(date, city)
    )""")

    # ── Events Calendar ──────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS events (
        event_id INTEGER DEFAULT nextval('seq_events') PRIMARY KEY,
        date VARCHAR NOT NULL,
        event_name VARCHAR NOT NULL,
        event_type VARCHAR NOT NULL,
        city VARCHAR,
        impact_multiplier DOUBLE DEFAULT 1.0,
        affected_categories VARCHAR
    )""")

    # ── Sales History ────────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        sale_id INTEGER DEFAULT nextval('seq_sales') PRIMARY KEY,
        date VARCHAR NOT NULL,
        store_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        qty_ordered DOUBLE NOT NULL,
        qty_sold DOUBLE NOT NULL,
        qty_wasted DOUBLE NOT NULL,
        revenue DOUBLE NOT NULL,
        waste_cost DOUBLE NOT NULL,
        weather_temp DOUBLE,
        event_flag INTEGER DEFAULT 0,
        day_of_week INTEGER,
        month INTEGER
    )""")

    # ── Demand Forecasts ─────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS forecasts (
        forecast_id INTEGER DEFAULT nextval('seq_forecasts') PRIMARY KEY,
        created_at VARCHAR NOT NULL,
        store_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        forecast_date VARCHAR NOT NULL,
        predicted_demand DOUBLE NOT NULL,
        lower_bound DOUBLE,
        upper_bound DOUBLE,
        model_used VARCHAR,
        confidence DOUBLE
    )""")

    # ── Waste Cascade Actions ────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS waste_cascade_actions (
        action_id INTEGER DEFAULT nextval('seq_cascade') PRIMARY KEY,
        created_at VARCHAR NOT NULL,
        source_store_id INTEGER NOT NULL,
        destination_store_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity_kg DOUBLE NOT NULL,
        cascade_tier INTEGER NOT NULL,
        carbon_saved_kg DOUBLE NOT NULL,
        cost_saved DOUBLE NOT NULL,
        status VARCHAR DEFAULT 'planned'
    )""")

    # ── Route Plans ──────────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS routes (
        route_id INTEGER DEFAULT nextval('seq_routes') PRIMARY KEY,
        created_at VARCHAR NOT NULL,
        vehicle_id VARCHAR,
        total_distance_km DOUBLE,
        total_time_minutes DOUBLE,
        total_load_kg DOUBLE,
        stops_json VARCHAR,
        carbon_emission_kg DOUBLE,
        status VARCHAR DEFAULT 'planned'
    )""")

    # ── Carbon Impact Log ────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS carbon_impact (
        id INTEGER DEFAULT nextval('seq_carbon') PRIMARY KEY,
        date VARCHAR NOT NULL,
        action_type VARCHAR NOT NULL,
        description VARCHAR,
        food_saved_kg DOUBLE DEFAULT 0,
        carbon_saved_kg DOUBLE DEFAULT 0,
        cost_saved DOUBLE DEFAULT 0,
        store_id INTEGER
    )""")

    # ── Inventory Snapshots ──────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER DEFAULT nextval('seq_inventory') PRIMARY KEY,
        date VARCHAR NOT NULL,
        store_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity_on_hand DOUBLE NOT NULL,
        days_until_expiry INTEGER,
        freshness_score DOUBLE,
        UNIQUE(date, store_id, product_id)
    )""")

    conn.close()
    print("✅ Database initialized successfully at:", DB_PATH)


def reset_database():
    """Drop and recreate the database."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    for ext in [".wal", ".tmp"]:
        p = DB_PATH + ext
        if os.path.exists(p):
            os.remove(p)
    init_database()
    print("🔄 Database reset complete.")


if __name__ == "__main__":
    init_database()
