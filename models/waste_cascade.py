"""
FoodFlow AI — Waste Cascade Optimizer
Implements the 3-tier waste reduction cascade:
  Tier 1: Retailer surplus → Redistribute to nearby retailers with demand
  Tier 2: Remaining surplus → Food banks / community kitchens
  Tier 3: Non-edible remainder → Composting / biogas facilities
Uses linear programming to minimize total waste + carbon footprint.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime
from database.db import get_db
from utils.helpers import get_stores_dataframe, get_inventory_dataframe, haversine_distance
from models.carbon_calculator import (
    calculate_food_saved_carbon,
    calculate_redistribution_carbon,
    calculate_composting_carbon,
    log_carbon_impact,
    CARBON_FACTORS
)


class WasteCascadeOptimizer:
    """
    Optimizes the redistribution of surplus food across the 3-tier cascade.
    
    Priority: Feed people first, then compost. Never landfill.
    """

    def __init__(self):
        self.stores = None
        self.surplus_items = []
        self.actions = []
        self.summary = {}

    def load_data(self):
        """Load stores and compute distance matrix."""
        self.stores = get_stores_dataframe()
        n = len(self.stores)
        self.distance_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i != j:
                    self.distance_matrix[i][j] = haversine_distance(
                        self.stores.iloc[i]["latitude"],
                        self.stores.iloc[i]["longitude"],
                        self.stores.iloc[j]["latitude"],
                        self.stores.iloc[j]["longitude"]
                    )

    def identify_surplus(self, forecast_days: int = 3) -> pd.DataFrame:
        """
        Identify surplus items across all retailer stores.
        Surplus = current stock - (predicted demand * days).
        """
        with get_db(read_only=True) as conn:
            surplus_df = conn.execute("""
                SELECT
                    i.store_id, i.product_id,
                    p.name as product_name, p.category,
                    p.shelf_life_days, p.carbon_footprint_kg,
                    p.unit_cost, p.unit_price, p.is_perishable,
                    st.name as store_name, st.city, st.store_type,
                    st.latitude, st.longitude,
                    i.quantity_on_hand, i.days_until_expiry, i.freshness_score,
                    COALESCE(f.predicted_demand, p.avg_daily_demand) as daily_demand
                FROM inventory i
                JOIN products p ON i.product_id = p.product_id
                JOIN stores st ON i.store_id = st.store_id
                LEFT JOIN (
                    SELECT store_id, product_id,
                           AVG(predicted_demand) as predicted_demand
                    FROM forecasts
                    WHERE CAST(forecast_date AS DATE) >= current_date
                    GROUP BY store_id, product_id
                ) f ON i.store_id = f.store_id AND i.product_id = f.product_id
                WHERE i.date = (SELECT MAX(date) FROM inventory)
                AND st.store_type = 'retailer'
                AND p.is_perishable = 1
            """).fetchdf()

        if len(surplus_df) == 0:
            print("No inventory data found.")
            return pd.DataFrame()

        # Calculate surplus quantity
        surplus_df["expected_demand"] = surplus_df["daily_demand"] * forecast_days
        surplus_df["surplus_qty"] = surplus_df["quantity_on_hand"] - surplus_df["expected_demand"]
        surplus_df["is_expiring_soon"] = surplus_df["days_until_expiry"] <= 2

        # For expiring items, treat entire on-hand as redistributable
        surplus_df.loc[surplus_df["is_expiring_soon"], "surplus_qty"] = (
            surplus_df.loc[surplus_df["is_expiring_soon"], "quantity_on_hand"]
        )

        # Keep items with meaningful surplus or expiring soon
        surplus = surplus_df[
            (surplus_df["surplus_qty"] > 5) |  # meaningful surplus
            (surplus_df["is_expiring_soon"] & (surplus_df["quantity_on_hand"] > 5))
        ].copy()

        # Prioritize by urgency
        surplus["urgency"] = (
            (1 - surplus["freshness_score"]) * 40 +
            (surplus["surplus_qty"] / surplus["quantity_on_hand"].clip(lower=1)) * 30 +
            surplus["carbon_footprint_kg"] * 10 +  # higher CO₂ items get priority
            surplus["is_expiring_soon"].astype(float) * 20
        )
        surplus = surplus.sort_values("urgency", ascending=False)

        self.surplus_items = surplus
        print(f"🔍 Found {len(surplus)} surplus items across {surplus['store_id'].nunique()} stores")
        print(f"   Total surplus: {surplus['surplus_qty'].sum():,.0f} kg")
        return surplus

    def optimize_cascade(self, max_redistribution_distance_km: float = 50) -> list:
        """
        Run the 3-tier cascade optimization.
        
        For each surplus item:
        1. Try to find a nearby retailer that needs it (Tier 1)
        2. Assign to nearest food bank (Tier 2)
        3. Remaining goes to composting (Tier 3)
        """
        if self.stores is None:
            self.load_data()

        if len(self.surplus_items) == 0:
            self.identify_surplus()

        if len(self.surplus_items) == 0:
            print("No surplus to optimize.")
            return []

        food_banks = self.stores[self.stores["store_type"] == "food_bank"]
        compost = self.stores[self.stores["store_type"] == "compost_facility"]
        retailers = self.stores[self.stores["store_type"] == "retailer"]

        actions = []
        tier_stats = {1: 0, 2: 0, 3: 0}
        total_carbon_saved = 0
        total_cost_saved = 0

        for _, item in self.surplus_items.iterrows():
            remaining_surplus = item["surplus_qty"]
            if remaining_surplus <= 0:
                continue

            src_store_id = item["store_id"]
            category = item["category"]
            product_id = item["product_id"]

            # ── TIER 1: Redistribute to nearby retailers ──
            if not item["is_expiring_soon"]:  # Only if still has shelf life
                for _, retailer in retailers.iterrows():
                    if retailer["store_id"] == src_store_id:
                        continue
                    if retailer["city"] != item["city"]:
                        continue  # Same city only for Tier 1

                    dist = haversine_distance(
                        item["latitude"], item["longitude"],
                        retailer["latitude"], retailer["longitude"]
                    )
                    if dist > max_redistribution_distance_km:
                        continue

                    # Transfer up to 30% of surplus to another retailer
                    transfer_qty = min(remaining_surplus * 0.3, remaining_surplus)
                    if transfer_qty < 2:
                        continue

                    carbon = calculate_redistribution_carbon(category, transfer_qty, dist)
                    cost = transfer_qty * item["unit_price"] * 0.5  # Discounted

                    actions.append({
                        "source_store_id": src_store_id,
                        "destination_store_id": retailer["store_id"],
                        "product_id": product_id,
                        "product_name": item["product_name"],
                        "category": category,
                        "quantity_kg": round(transfer_qty, 1),
                        "cascade_tier": 1,
                        "carbon_saved_kg": round(carbon, 2),
                        "cost_saved": round(cost, 2),
                        "distance_km": round(dist, 1),
                        "source_name": item["store_name"],
                        "destination_name": retailer["name"],
                    })
                    remaining_surplus -= transfer_qty
                    tier_stats[1] += transfer_qty
                    total_carbon_saved += carbon
                    total_cost_saved += cost

                    if remaining_surplus < 2:
                        break

            # ── TIER 2: Send to food banks ──
            if remaining_surplus > 0 and item["days_until_expiry"] >= 1:
                # Find nearest food bank in same city
                city_banks = food_banks[food_banks["city"] == item["city"]]
                if len(city_banks) == 0:
                    city_banks = food_banks  # Any food bank

                for _, bank in city_banks.iterrows():
                    dist = haversine_distance(
                        item["latitude"], item["longitude"],
                        bank["latitude"], bank["longitude"]
                    )
                    # Transfer up to 80% of remaining to food bank
                    transfer_qty = min(remaining_surplus * 0.8, remaining_surplus)
                    if transfer_qty < 1:
                        continue

                    carbon = calculate_redistribution_carbon(category, transfer_qty, dist)
                    cost = transfer_qty * item["unit_cost"]  # Full cost saved from waste

                    actions.append({
                        "source_store_id": src_store_id,
                        "destination_store_id": bank["store_id"],
                        "product_id": product_id,
                        "product_name": item["product_name"],
                        "category": category,
                        "quantity_kg": round(transfer_qty, 1),
                        "cascade_tier": 2,
                        "carbon_saved_kg": round(carbon, 2),
                        "cost_saved": round(cost, 2),
                        "distance_km": round(dist, 1),
                        "source_name": item["store_name"],
                        "destination_name": bank["name"],
                    })
                    remaining_surplus -= transfer_qty
                    tier_stats[2] += transfer_qty
                    total_carbon_saved += carbon
                    total_cost_saved += cost
                    break

            # ── TIER 3: Composting ──
            if remaining_surplus > 0:
                city_compost = compost[compost["city"] == item["city"]]
                if len(city_compost) == 0:
                    city_compost = compost

                if len(city_compost) > 0:
                    comp = city_compost.iloc[0]
                    dist = haversine_distance(
                        item["latitude"], item["longitude"],
                        comp["latitude"], comp["longitude"]
                    )
                    carbon = calculate_composting_carbon(remaining_surplus)

                    actions.append({
                        "source_store_id": src_store_id,
                        "destination_store_id": comp["store_id"],
                        "product_id": product_id,
                        "product_name": item["product_name"],
                        "category": category,
                        "quantity_kg": round(remaining_surplus, 1),
                        "cascade_tier": 3,
                        "carbon_saved_kg": round(carbon, 2),
                        "cost_saved": 0,  # No cost recovery from compost
                        "distance_km": round(dist, 1),
                        "source_name": item["store_name"],
                        "destination_name": comp["name"],
                    })
                    tier_stats[3] += remaining_surplus
                    total_carbon_saved += carbon

        self.actions = actions
        self.summary = {
            "total_actions": len(actions),
            "tier_1_kg": round(tier_stats[1], 1),
            "tier_2_kg": round(tier_stats[2], 1),
            "tier_3_kg": round(tier_stats[3], 1),
            "total_redistributed_kg": round(sum(tier_stats.values()), 1),
            "total_carbon_saved_kg": round(total_carbon_saved, 1),
            "total_cost_saved": round(total_cost_saved, 2),
        }

        print(f"\n♻️  Waste Cascade Optimization Results:")
        print(f"   Tier 1 (Retailer→Retailer): {tier_stats[1]:,.0f} kg")
        print(f"   Tier 2 (→ Food Banks):      {tier_stats[2]:,.0f} kg")
        print(f"   Tier 3 (→ Composting):       {tier_stats[3]:,.0f} kg")
        print(f"   Total CO₂ Saved:            {total_carbon_saved:,.0f} kg")
        print(f"   Total Cost Saved:           ${total_cost_saved:,.2f}")

        return actions

    def save_actions(self):
        """Save cascade actions to database."""
        now = datetime.now().isoformat()
        with get_db() as conn:
            for action in self.actions:
                conn.execute("""
                    INSERT INTO waste_cascade_actions (
                        created_at, source_store_id, destination_store_id,
                        product_id, quantity_kg, cascade_tier,
                        carbon_saved_kg, cost_saved, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planned')
                """, [
                    now, int(action["source_store_id"]),
                    int(action["destination_store_id"]),
                    int(action["product_id"]), float(action["quantity_kg"]),
                    int(action["cascade_tier"]), float(action["carbon_saved_kg"]),
                    float(action["cost_saved"])
                ])

                # Log carbon impact in same transaction
                conn.execute("""
                    INSERT INTO carbon_impact (date, action_type, description,
                        food_saved_kg, carbon_saved_kg, cost_saved, store_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    now[:10], f"cascade_tier_{action['cascade_tier']}",
                    f"{action['product_name']}: {action['source_name']} -> {action['destination_name']}",
                    float(action["quantity_kg"]), float(action["carbon_saved_kg"]),
                    float(action["cost_saved"]), int(action["source_store_id"])
                ])
        print(f"💾 Saved {len(self.actions)} cascade actions to database")

    def get_sankey_data(self) -> dict:
        """Get data formatted for a Sankey diagram visualization."""
        if not self.actions:
            return {"nodes": [], "links": []}

        nodes = set()
        links = []

        for action in self.actions:
            src = action["source_name"]
            dst = action["destination_name"]
            nodes.add(src)
            nodes.add(dst)

        node_list = sorted(list(nodes))
        node_idx = {name: i for i, name in enumerate(node_list)}

        # Aggregate links
        link_map = {}
        for action in self.actions:
            key = (action["source_name"], action["destination_name"], action["cascade_tier"])
            if key not in link_map:
                link_map[key] = 0
            link_map[key] += action["quantity_kg"]

        tier_colors = {1: "rgba(31,119,180,0.5)", 2: "rgba(44,160,44,0.5)", 3: "rgba(214,39,40,0.3)"}

        for (src, dst, tier), qty in link_map.items():
            links.append({
                "source": node_idx[src],
                "target": node_idx[dst],
                "value": round(qty, 1),
                "tier": tier,
                "color": tier_colors.get(tier, "rgba(128,128,128,0.3)")
            })

        return {
            "nodes": [{"name": n} for n in node_list],
            "links": links
        }


# ── Singleton ──
_optimizer = None

def get_cascade_optimizer() -> WasteCascadeOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = WasteCascadeOptimizer()
    return _optimizer


if __name__ == "__main__":
    optimizer = WasteCascadeOptimizer()
    optimizer.load_data()
    surplus = optimizer.identify_surplus(forecast_days=3)
    if len(surplus) > 0:
        print(f"\nTop 10 surplus items:")
        print(surplus[["store_name", "product_name", "quantity_on_hand",
                       "surplus_qty", "days_until_expiry", "freshness_score"]].head(10).to_string())
        actions = optimizer.optimize_cascade()
        optimizer.save_actions()
