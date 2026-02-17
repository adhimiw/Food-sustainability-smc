"""
FoodFlow AI — Shared Utility Functions
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db import get_db


def get_sales_dataframe(store_id=None, product_id=None, days_back=None):
    """Load sales data as a pandas DataFrame with optional filters."""
    query = """
        SELECT s.*, p.name as product_name, p.category, p.subcategory,
               p.shelf_life_days, p.carbon_footprint_kg, p.is_perishable,
               p.unit_cost, p.unit_price,
               st.name as store_name, st.city, st.store_type
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        JOIN stores st ON s.store_id = st.store_id
        WHERE 1=1
    """
    params = []
    if store_id:
        query += " AND s.store_id = ?"
        params.append(store_id)
    if product_id:
        query += " AND s.product_id = ?"
        params.append(product_id)
    if days_back:
        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        query += " AND s.date >= ?"
        params.append(cutoff)

    query += " ORDER BY s.date"

    with get_db(read_only=True) as conn:
        df = conn.execute(query, params).fetchdf() if params else conn.execute(query).fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_products_dataframe():
    """Load all products."""
    with get_db(read_only=True) as conn:
        return conn.execute("SELECT * FROM products").fetchdf()


def get_stores_dataframe(store_type=None):
    """Load stores with optional type filter."""
    if store_type:
        with get_db(read_only=True) as conn:
            return conn.execute("SELECT * FROM stores WHERE store_type = ?", [store_type]).fetchdf()
    with get_db(read_only=True) as conn:
        return conn.execute("SELECT * FROM stores").fetchdf()


def get_weather_dataframe(city=None, days_back=None):
    """Load weather data."""
    query = "SELECT * FROM weather WHERE 1=1"
    params = []
    if city:
        query += " AND city = ?"
        params.append(city)
    if days_back:
        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        query += " AND date >= ?"
        params.append(cutoff)
    with get_db(read_only=True) as conn:
        df = conn.execute(query, params).fetchdf() if params else conn.execute(query).fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_events_dataframe(city=None):
    """Load events data."""
    if city:
        with get_db(read_only=True) as conn:
            df = conn.execute("SELECT * FROM events WHERE city = ?", [city]).fetchdf()
    else:
        with get_db(read_only=True) as conn:
            df = conn.execute("SELECT * FROM events").fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_inventory_dataframe(store_id=None, critical_only=False):
    """Load inventory data."""
    query = """
        SELECT i.*, p.name as product_name, p.category,
               p.shelf_life_days, p.carbon_footprint_kg,
               p.unit_cost, p.unit_price,
               st.name as store_name, st.city
        FROM inventory i
        JOIN products p ON i.product_id = p.product_id
        JOIN stores st ON i.store_id = st.store_id
        WHERE 1=1
    """
    params = []
    if store_id:
        query += " AND i.store_id = ?"
        params.append(store_id)
    if critical_only:
        query += " AND i.freshness_score < 0.3"

    with get_db(read_only=True) as conn:
        df = conn.execute(query, params).fetchdf() if params else conn.execute(query).fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    return df


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two GPS coordinates."""
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c


def format_currency(amount):
    """Format a number as currency."""
    return f"${amount:,.2f}"


def format_weight(kg):
    """Format weight with appropriate unit."""
    if kg >= 1000:
        return f"{kg/1000:,.1f} tonnes"
    return f"{kg:,.1f} kg"


def format_co2(kg):
    """Format CO2 with appropriate unit."""
    if kg >= 1000:
        return f"{kg/1000:,.1f} tonnes CO₂"
    return f"{kg:,.1f} kg CO₂"


def get_waste_summary():
    """Get overall waste statistics."""
    with get_db(read_only=True) as conn:
        df = conn.execute("""
            SELECT
                SUM(qty_wasted) as total_waste_kg,
                SUM(waste_cost) as total_waste_cost,
                SUM(qty_sold) as total_sold_kg,
                SUM(revenue) as total_revenue,
                COUNT(DISTINCT date) as num_days,
                COUNT(DISTINCT store_id) as num_stores
            FROM sales
        """).fetchdf()
        if len(df) == 0:
            return {}
        return df.iloc[0].to_dict()


def get_daily_waste_trend():
    """Get daily waste aggregation."""
    with get_db(read_only=True) as conn:
        df = conn.execute("""
            SELECT date,
                   SUM(qty_wasted) as total_waste,
                   SUM(qty_sold) as total_sold,
                   SUM(waste_cost) as total_waste_cost,
                   SUM(revenue) as total_revenue
            FROM sales
            GROUP BY date
            ORDER BY date
        """).fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    df["waste_rate"] = df["total_waste"] / (df["total_sold"] + df["total_waste"]) * 100
    return df
