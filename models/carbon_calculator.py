"""
FoodFlow AI — Carbon Impact Calculator
Measures CO₂ savings from waste reduction and optimized distribution.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from database.db import get_db

# ── Carbon Emission Factors (kg CO₂ per kg of food) ─────────
# Source-based estimates combining production + disposal emissions
CARBON_FACTORS = {
    "Fruits": 0.9,
    "Vegetables": 0.7,
    "Dairy": 5.5,
    "Meat": 18.0,      # Weighted avg (poultry=6.9, beef=27, pork=12)
    "Seafood": 8.5,
    "Bakery": 1.2,
    "Beverages": 0.8,
    "Pantry": 1.0,
    "Frozen": 2.5,
    "Snacks": 1.8,
    "Deli": 3.0,
    "Baby": 2.0,
}

# Transport emission: ~0.1 kg CO₂ per km per tonne
TRANSPORT_EMISSION_PER_KM_PER_TONNE = 0.1

# Landfill decomposition produces ~2.5 kg CO₂e per kg of food waste (methane)
LANDFILL_EMISSION_PER_KG = 2.5

# Compost vs landfill savings: composting emits ~0.3 kg CO₂ vs landfill's 2.5
COMPOST_EMISSION_PER_KG = 0.3


def calculate_food_saved_carbon(category: str, quantity_kg: float) -> float:
    """
    Calculate CO₂ saved by preventing food waste.
    Combines production emissions + landfill avoidance.
    """
    production_co2 = CARBON_FACTORS.get(category, 1.5) * quantity_kg
    landfill_co2 = LANDFILL_EMISSION_PER_KG * quantity_kg
    return round(production_co2 + landfill_co2, 2)


def calculate_redistribution_carbon(category: str, quantity_kg: float,
                                     distance_km: float) -> float:
    """
    Net CO₂ savings from redistributing surplus food to food banks.
    = (production CO₂ + landfill CO₂ saved) - transport CO₂
    """
    saved = calculate_food_saved_carbon(category, quantity_kg)
    transport_co2 = TRANSPORT_EMISSION_PER_KM_PER_TONNE * distance_km * (quantity_kg / 1000)
    return round(saved - transport_co2, 2)


def calculate_composting_carbon(quantity_kg: float) -> float:
    """
    CO₂ savings from composting vs landfill.
    """
    return round((LANDFILL_EMISSION_PER_KG - COMPOST_EMISSION_PER_KG) * quantity_kg, 2)


def calculate_transport_emissions(distance_km: float, load_kg: float) -> float:
    """Calculate transport CO₂ emissions."""
    return round(TRANSPORT_EMISSION_PER_KM_PER_TONNE * distance_km * (load_kg / 1000), 2)


def calculate_route_carbon_savings(optimized_distance_km: float,
                                    naive_distance_km: float,
                                    load_kg: float) -> float:
    """CO₂ saved by route optimization."""
    naive_co2 = calculate_transport_emissions(naive_distance_km, load_kg)
    optimized_co2 = calculate_transport_emissions(optimized_distance_km, load_kg)
    return round(naive_co2 - optimized_co2, 2)


def get_carbon_summary():
    """Get overall carbon impact metrics from the database."""
    with get_db(read_only=True) as conn:
        # Get waste by category
        cat_df = conn.execute("""
            SELECT p.category, SUM(s.qty_wasted) as total_waste_kg
            FROM sales s
            JOIN products p ON s.product_id = p.product_id
            GROUP BY p.category
        """).fetchdf()

        total_waste_co2 = 0
        category_breakdown = {}
        for _, row in cat_df.iterrows():
            cat = row["category"]
            waste_kg = float(row["total_waste_kg"])
            co2 = calculate_food_saved_carbon(cat, waste_kg)
            category_breakdown[cat] = {
                "waste_kg": round(waste_kg, 1),
                "co2_impact_kg": round(co2, 1)
            }
            total_waste_co2 += co2

        # Get cascade savings
        cascade_savings = conn.execute("""
            SELECT COALESCE(SUM(carbon_saved_kg), 0) as total_saved
            FROM waste_cascade_actions
            WHERE status != 'cancelled'
        """).fetchone()[0]

        # Get route savings
        route_count = conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0]

    return {
        "total_waste_co2_kg": round(total_waste_co2, 1),
        "cascade_savings_co2_kg": round(float(cascade_savings), 1),
        "category_breakdown": category_breakdown,
        "total_routes_optimized": int(route_count),
        "potential_savings_pct": 30  # target: 30% reduction
    }


def log_carbon_impact(date: str, action_type: str, description: str,
                       food_saved_kg: float = 0, carbon_saved_kg: float = 0,
                       cost_saved: float = 0, store_id: int = None):
    """Log a carbon impact event to the database."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO carbon_impact (date, action_type, description,
                food_saved_kg, carbon_saved_kg, cost_saved, store_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date, action_type, description, food_saved_kg,
              carbon_saved_kg, cost_saved, store_id))


def get_equivalencies(co2_kg: float) -> dict:
    """Convert CO₂ savings to human-understandable equivalencies."""
    return {
        "trees_planted": round(co2_kg / 21, 1),        # 1 tree absorbs ~21 kg CO₂/year
        "car_km_avoided": round(co2_kg / 0.21, 0),     # avg car emits 0.21 kg CO₂/km
        "flights_avoided": round(co2_kg / 255, 2),     # short-haul flight ~255 kg CO₂
        "homes_powered_days": round(co2_kg / 18.3, 1), # avg home ~18.3 kg CO₂/day
        "smartphones_charged": round(co2_kg / 0.008, 0) # ~8g CO₂ per charge
    }


if __name__ == "__main__":
    # Demo
    print("Carbon Calculator Demo")
    print("=" * 40)
    print(f"Saving 100kg of Meat: {calculate_food_saved_carbon('Meat', 100)} kg CO₂")
    print(f"Saving 100kg of Vegetables: {calculate_food_saved_carbon('Vegetables', 100)} kg CO₂")
    print(f"Redistributing 50kg Dairy over 20km: {calculate_redistribution_carbon('Dairy', 50, 20)} kg CO₂")
    print(f"Composting 200kg: {calculate_composting_carbon(200)} kg CO₂")

    eq = get_equivalencies(5000)
    print(f"\n5000 kg CO₂ equivalent to:")
    for k, v in eq.items():
        print(f"  {k}: {v}")
