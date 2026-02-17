"""
FoodFlow AI — Synthetic Dataset Generator
Generates realistic, correlated food supply chain data for 2 years.
Covers: products, stores, suppliers, weather, events, sales, inventory.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import math
import numpy as np
import pandas as pd
import argparse
from datetime import datetime, timedelta
from database.db import init_database, reset_database, get_db

# ── Reproducibility ──────────────────────────────────────────
DEFAULT_SEED = 42


def set_random_seed(seed: int = DEFAULT_SEED):
    """Set Python and NumPy RNG seeds."""
    random.seed(seed)
    np.random.seed(seed)


set_random_seed(DEFAULT_SEED)

# ── Configuration ────────────────────────────────────────────
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 12, 31)
NUM_DAYS = (END_DATE - START_DATE).days + 1
CITIES = ["Metro City", "Green Valley", "Harbor Town"]

# ══════════════════════════════════════════════════════════════
#  PRODUCT CATALOG — 200+ realistic items
# ══════════════════════════════════════════════════════════════

PRODUCT_DEFS = [
    # (name, category, subcategory, shelf_life, avg_demand, cost, price, co2_kg, perishable)
    # ── Fruits ──
    ("Bananas", "Fruits", "Tropical", 7, 120, 0.8, 1.5, 0.9, 1),
    ("Apples - Red", "Fruits", "Pome", 21, 90, 1.2, 2.0, 0.4, 1),
    ("Apples - Green", "Fruits", "Pome", 21, 60, 1.3, 2.1, 0.4, 1),
    ("Oranges", "Fruits", "Citrus", 14, 85, 1.0, 1.8, 0.5, 1),
    ("Strawberries", "Fruits", "Berries", 5, 50, 2.5, 4.5, 1.1, 1),
    ("Blueberries", "Fruits", "Berries", 7, 35, 3.0, 5.5, 0.8, 1),
    ("Grapes - Red", "Fruits", "Vine", 10, 55, 2.0, 3.5, 0.7, 1),
    ("Grapes - Green", "Fruits", "Vine", 10, 45, 2.1, 3.6, 0.7, 1),
    ("Watermelon", "Fruits", "Melon", 14, 30, 3.0, 5.0, 0.3, 1),
    ("Mangoes", "Fruits", "Tropical", 8, 40, 2.5, 4.0, 1.5, 1),
    ("Pineapple", "Fruits", "Tropical", 7, 25, 2.0, 3.5, 0.6, 1),
    ("Avocados", "Fruits", "Tropical", 5, 70, 1.5, 3.0, 2.5, 1),
    ("Peaches", "Fruits", "Stone", 7, 35, 1.8, 3.2, 0.5, 1),
    ("Pears", "Fruits", "Pome", 14, 40, 1.3, 2.2, 0.3, 1),
    ("Lemons", "Fruits", "Citrus", 21, 50, 0.8, 1.5, 0.3, 1),
    ("Limes", "Fruits", "Citrus", 14, 30, 0.9, 1.6, 0.4, 1),
    ("Kiwi", "Fruits", "Exotic", 14, 25, 1.5, 2.8, 1.0, 1),
    ("Pomegranate", "Fruits", "Exotic", 21, 20, 2.5, 4.5, 0.8, 1),
    ("Cherries", "Fruits", "Stone", 5, 20, 4.0, 7.0, 0.6, 1),
    ("Raspberries", "Fruits", "Berries", 4, 25, 3.5, 6.0, 1.0, 1),

    # ── Vegetables ──
    ("Tomatoes", "Vegetables", "Nightshade", 10, 100, 1.0, 2.0, 1.4, 1),
    ("Potatoes", "Vegetables", "Root", 30, 130, 0.6, 1.2, 0.5, 1),
    ("Onions", "Vegetables", "Allium", 30, 110, 0.5, 1.0, 0.3, 1),
    ("Carrots", "Vegetables", "Root", 21, 80, 0.7, 1.3, 0.4, 1),
    ("Broccoli", "Vegetables", "Cruciferous", 7, 55, 1.5, 2.8, 0.9, 1),
    ("Cauliflower", "Vegetables", "Cruciferous", 7, 40, 1.6, 2.9, 0.8, 1),
    ("Spinach", "Vegetables", "Leafy", 5, 60, 1.2, 2.5, 0.6, 1),
    ("Lettuce - Iceberg", "Vegetables", "Leafy", 7, 75, 0.8, 1.8, 0.5, 1),
    ("Lettuce - Romaine", "Vegetables", "Leafy", 7, 50, 1.0, 2.0, 0.5, 1),
    ("Bell Peppers - Red", "Vegetables", "Nightshade", 10, 45, 1.5, 2.8, 0.9, 1),
    ("Bell Peppers - Green", "Vegetables", "Nightshade", 10, 50, 1.2, 2.2, 0.8, 1),
    ("Cucumbers", "Vegetables", "Gourd", 7, 65, 0.6, 1.2, 0.4, 1),
    ("Zucchini", "Vegetables", "Gourd", 7, 35, 1.0, 2.0, 0.3, 1),
    ("Mushrooms", "Vegetables", "Fungi", 5, 40, 2.0, 3.5, 0.6, 1),
    ("Sweet Corn", "Vegetables", "Grain", 5, 50, 0.8, 1.5, 1.0, 1),
    ("Green Beans", "Vegetables", "Legume", 7, 35, 1.2, 2.2, 0.5, 1),
    ("Celery", "Vegetables", "Stalk", 14, 30, 0.7, 1.3, 0.3, 1),
    ("Cabbage", "Vegetables", "Cruciferous", 14, 45, 0.5, 1.0, 0.2, 1),
    ("Eggplant", "Vegetables", "Nightshade", 7, 25, 1.3, 2.5, 0.7, 1),
    ("Garlic", "Vegetables", "Allium", 60, 70, 1.5, 3.0, 0.5, 1),
    ("Ginger", "Vegetables", "Root", 30, 25, 2.0, 4.0, 0.7, 1),
    ("Asparagus", "Vegetables", "Stalk", 5, 20, 3.0, 5.5, 0.9, 1),
    ("Peas", "Vegetables", "Legume", 5, 30, 1.5, 2.8, 0.4, 1),
    ("Radishes", "Vegetables", "Root", 10, 20, 0.8, 1.5, 0.2, 1),
    ("Sweet Potatoes", "Vegetables", "Root", 21, 45, 1.0, 2.0, 0.5, 1),

    # ── Dairy ──
    ("Whole Milk 1L", "Dairy", "Milk", 7, 150, 1.0, 1.8, 3.2, 1),
    ("Skim Milk 1L", "Dairy", "Milk", 7, 80, 0.9, 1.6, 2.8, 1),
    ("Cheddar Cheese 200g", "Dairy", "Cheese", 30, 60, 2.5, 4.5, 8.5, 1),
    ("Mozzarella 200g", "Dairy", "Cheese", 14, 55, 2.0, 3.8, 7.0, 1),
    ("Greek Yogurt 500g", "Dairy", "Yogurt", 14, 70, 1.5, 3.0, 2.5, 1),
    ("Plain Yogurt 500g", "Dairy", "Yogurt", 14, 50, 1.2, 2.2, 2.0, 1),
    ("Butter 250g", "Dairy", "Butter", 30, 55, 2.0, 3.5, 9.0, 1),
    ("Cream Cheese 200g", "Dairy", "Cheese", 14, 30, 1.8, 3.2, 5.0, 1),
    ("Heavy Cream 500ml", "Dairy", "Cream", 10, 25, 2.5, 4.0, 4.0, 1),
    ("Eggs - Dozen", "Dairy", "Eggs", 21, 100, 2.0, 3.5, 4.8, 1),
    ("Cottage Cheese 250g", "Dairy", "Cheese", 10, 20, 1.5, 2.8, 3.5, 1),
    ("Sour Cream 200ml", "Dairy", "Cream", 14, 25, 1.0, 2.0, 3.0, 1),

    # ── Meat ──
    ("Chicken Breast 500g", "Meat", "Poultry", 3, 80, 3.5, 6.5, 6.9, 1),
    ("Chicken Thighs 500g", "Meat", "Poultry", 3, 60, 2.8, 5.0, 6.9, 1),
    ("Ground Beef 500g", "Meat", "Red Meat", 3, 65, 4.0, 7.5, 27.0, 1),
    ("Beef Steak 300g", "Meat", "Red Meat", 3, 35, 6.0, 12.0, 27.0, 1),
    ("Pork Chops 500g", "Meat", "Pork", 3, 40, 3.0, 5.5, 12.1, 1),
    ("Ground Pork 500g", "Meat", "Pork", 3, 35, 2.8, 5.0, 12.1, 1),
    ("Bacon 250g", "Meat", "Pork", 7, 50, 3.5, 6.0, 12.1, 1),
    ("Sausages 500g", "Meat", "Processed", 7, 45, 2.5, 4.5, 8.0, 1),
    ("Turkey Breast 500g", "Meat", "Poultry", 3, 30, 4.0, 7.0, 5.5, 1),
    ("Lamb Chops 500g", "Meat", "Red Meat", 3, 20, 7.0, 13.0, 39.2, 1),
    ("Ham Sliced 200g", "Meat", "Processed", 10, 40, 2.0, 3.5, 8.0, 1),
    ("Salami 150g", "Meat", "Processed", 21, 25, 2.5, 4.5, 8.0, 1),

    # ── Seafood ──
    ("Salmon Fillet 300g", "Seafood", "Fish", 2, 35, 5.0, 9.0, 11.9, 1),
    ("Shrimp 500g", "Seafood", "Shellfish", 2, 25, 6.0, 11.0, 18.0, 1),
    ("Cod Fillet 300g", "Seafood", "Fish", 2, 20, 4.0, 7.5, 5.4, 1),
    ("Tuna Steak 300g", "Seafood", "Fish", 2, 15, 5.5, 10.0, 6.1, 1),
    ("Tilapia Fillet 300g", "Seafood", "Fish", 2, 25, 3.0, 5.5, 4.0, 1),
    ("Canned Tuna 170g", "Seafood", "Canned", 730, 40, 1.5, 2.5, 6.1, 0),
    ("Canned Salmon 200g", "Seafood", "Canned", 730, 20, 2.0, 3.5, 5.0, 0),

    # ── Bakery ──
    ("White Bread Loaf", "Bakery", "Bread", 5, 100, 1.0, 2.0, 0.8, 1),
    ("Whole Wheat Bread", "Bakery", "Bread", 5, 70, 1.2, 2.5, 0.7, 1),
    ("Sourdough Bread", "Bakery", "Bread", 5, 40, 2.0, 3.5, 0.6, 1),
    ("Croissants 4pk", "Bakery", "Pastry", 3, 35, 2.5, 4.5, 1.1, 1),
    ("Bagels 6pk", "Bakery", "Bread", 5, 30, 2.0, 3.5, 0.9, 1),
    ("Muffins 4pk", "Bakery", "Pastry", 3, 25, 2.5, 4.0, 1.0, 1),
    ("Burger Buns 8pk", "Bakery", "Bread", 5, 40, 1.5, 2.5, 0.8, 1),
    ("Tortillas 10pk", "Bakery", "Flatbread", 14, 45, 1.5, 2.8, 0.7, 1),
    ("Donuts 6pk", "Bakery", "Pastry", 2, 30, 2.5, 4.5, 1.2, 1),
    ("Cake - Chocolate", "Bakery", "Cake", 5, 15, 5.0, 9.0, 2.0, 1),

    # ── Beverages ──
    ("Orange Juice 1L", "Beverages", "Juice", 10, 60, 1.5, 3.0, 0.7, 1),
    ("Apple Juice 1L", "Beverages", "Juice", 10, 45, 1.2, 2.5, 0.5, 1),
    ("Almond Milk 1L", "Beverages", "Plant Milk", 30, 35, 2.0, 3.5, 0.7, 1),
    ("Oat Milk 1L", "Beverages", "Plant Milk", 14, 40, 1.8, 3.0, 0.3, 1),
    ("Sparkling Water 1L", "Beverages", "Water", 365, 50, 0.5, 1.0, 0.2, 0),
    ("Cola 2L", "Beverages", "Soda", 180, 55, 0.8, 1.5, 0.4, 0),
    ("Green Tea 20pk", "Beverages", "Tea", 365, 25, 2.0, 3.5, 0.1, 0),
    ("Coffee Beans 500g", "Beverages", "Coffee", 180, 30, 5.0, 9.0, 8.0, 0),

    # ── Pantry / Dry Goods ──
    ("White Rice 1kg", "Pantry", "Grains", 365, 60, 1.2, 2.0, 2.7, 0),
    ("Brown Rice 1kg", "Pantry", "Grains", 180, 35, 1.5, 2.5, 2.5, 0),
    ("Pasta - Spaghetti", "Pantry", "Pasta", 730, 70, 1.0, 1.8, 1.2, 0),
    ("Pasta - Penne", "Pantry", "Pasta", 730, 50, 1.0, 1.8, 1.2, 0),
    ("Canned Tomatoes 400g", "Pantry", "Canned", 730, 65, 0.8, 1.5, 0.6, 0),
    ("Olive Oil 500ml", "Pantry", "Oil", 365, 30, 3.5, 6.0, 3.5, 0),
    ("Vegetable Oil 1L", "Pantry", "Oil", 365, 40, 1.5, 2.5, 2.0, 0),
    ("All-Purpose Flour 1kg", "Pantry", "Baking", 365, 45, 0.8, 1.5, 0.7, 0),
    ("Sugar 1kg", "Pantry", "Baking", 730, 40, 0.7, 1.3, 0.6, 0),
    ("Salt 500g", "Pantry", "Seasoning", 1825, 35, 0.3, 0.8, 0.1, 0),
    ("Black Pepper 100g", "Pantry", "Seasoning", 730, 15, 1.5, 3.0, 0.8, 0),
    ("Peanut Butter 500g", "Pantry", "Spreads", 180, 30, 2.5, 4.0, 2.5, 0),
    ("Honey 500g", "Pantry", "Spreads", 730, 20, 3.5, 6.0, 0.5, 0),
    ("Breakfast Cereal 500g", "Pantry", "Cereal", 180, 50, 2.5, 4.0, 1.5, 0),
    ("Oats 1kg", "Pantry", "Cereal", 365, 35, 1.5, 2.5, 0.5, 0),
    ("Canned Beans 400g", "Pantry", "Canned", 730, 45, 0.8, 1.5, 0.4, 0),
    ("Lentils 500g", "Pantry", "Legumes", 365, 25, 1.0, 2.0, 0.9, 0),
    ("Chickpeas 400g", "Pantry", "Canned", 730, 30, 0.9, 1.6, 0.4, 0),
    ("Soy Sauce 250ml", "Pantry", "Condiment", 365, 20, 1.5, 2.5, 0.8, 0),
    ("Ketchup 500ml", "Pantry", "Condiment", 180, 35, 1.0, 2.0, 1.5, 0),
    ("Mustard 250ml", "Pantry", "Condiment", 365, 20, 1.0, 1.8, 0.6, 0),
    ("Mayonnaise 500ml", "Pantry", "Condiment", 90, 30, 1.5, 2.5, 2.0, 1),
    ("Pasta Sauce 500ml", "Pantry", "Sauce", 365, 40, 1.5, 2.8, 0.9, 0),
    ("Coconut Milk 400ml", "Pantry", "Canned", 365, 20, 1.2, 2.2, 1.0, 0),

    # ── Frozen ──
    ("Frozen Pizza", "Frozen", "Prepared", 180, 40, 3.0, 5.5, 2.5, 0),
    ("Frozen Vegetables 500g", "Frozen", "Vegetables", 365, 45, 1.5, 2.5, 0.8, 0),
    ("Ice Cream 1L", "Frozen", "Dessert", 180, 35, 3.0, 5.0, 3.5, 0),
    ("Frozen Berries 500g", "Frozen", "Fruit", 365, 25, 2.5, 4.5, 0.6, 0),
    ("Frozen Fish Sticks 500g", "Frozen", "Seafood", 180, 20, 2.5, 4.0, 5.0, 0),
    ("Frozen French Fries 1kg", "Frozen", "Prepared", 365, 50, 1.5, 2.5, 1.5, 0),
    ("Frozen Chicken Nuggets", "Frozen", "Prepared", 180, 35, 3.0, 5.0, 5.5, 0),

    # ── Snacks ──
    ("Potato Chips 200g", "Snacks", "Chips", 120, 50, 1.5, 3.0, 2.2, 0),
    ("Tortilla Chips 300g", "Snacks", "Chips", 120, 30, 2.0, 3.5, 2.0, 0),
    ("Mixed Nuts 250g", "Snacks", "Nuts", 180, 25, 3.5, 6.0, 1.5, 0),
    ("Granola Bars 6pk", "Snacks", "Bars", 180, 35, 2.0, 3.5, 1.0, 0),
    ("Dark Chocolate 100g", "Snacks", "Chocolate", 365, 30, 2.0, 3.5, 3.5, 0),
    ("Milk Chocolate 100g", "Snacks", "Chocolate", 365, 40, 1.5, 2.5, 3.5, 0),
    ("Crackers 200g", "Snacks", "Crackers", 180, 30, 1.5, 2.5, 0.8, 0),
    ("Popcorn 300g", "Snacks", "Popcorn", 120, 20, 1.5, 2.5, 0.5, 0),

    # ── Deli / Prepared ──
    ("Hummus 300g", "Deli", "Dips", 14, 30, 1.5, 3.0, 0.8, 1),
    ("Guacamole 250g", "Deli", "Dips", 5, 20, 2.5, 4.5, 1.5, 1),
    ("Fresh Pasta 400g", "Deli", "Prepared", 5, 25, 2.5, 4.5, 1.0, 1),
    ("Salad Mix 300g", "Deli", "Salad", 5, 55, 2.0, 3.5, 0.5, 1),
    ("Coleslaw 300g", "Deli", "Salad", 5, 20, 1.5, 2.8, 0.4, 1),
    ("Rotisserie Chicken", "Deli", "Prepared", 3, 25, 4.0, 8.0, 6.9, 1),
    ("Fresh Soup 500ml", "Deli", "Prepared", 5, 20, 2.5, 4.5, 1.5, 1),
    ("Sushi 8pc Pack", "Deli", "Prepared", 1, 15, 4.0, 8.0, 3.0, 1),

    # ── Baby & Personal ──
    ("Baby Food Pouch", "Baby", "Food", 180, 15, 1.5, 2.5, 1.0, 0),
    ("Infant Formula 400g", "Baby", "Formula", 365, 10, 12.0, 18.0, 3.0, 0),

    # ── Extra perishables to add variety ──
    ("Fresh Herbs - Basil", "Vegetables", "Herbs", 5, 20, 1.5, 3.0, 0.3, 1),
    ("Fresh Herbs - Cilantro", "Vegetables", "Herbs", 5, 18, 1.0, 2.0, 0.2, 1),
    ("Fresh Herbs - Parsley", "Vegetables", "Herbs", 7, 15, 1.0, 2.0, 0.2, 1),
    ("Tofu 400g", "Deli", "Plant Protein", 10, 25, 1.5, 2.5, 2.0, 1),
    ("Tempeh 300g", "Deli", "Plant Protein", 10, 12, 2.0, 3.5, 1.0, 1),
]

# ── Store Definitions ────────────────────────────────────────
STORE_DEFS = [
    # (name, type, lat, lon, capacity_kg, hours_start, hours_end, city)
    ("FreshMart Downtown", "retailer", 40.7128, -74.0060, 5000, 7, 23, "Metro City"),
    ("FreshMart Uptown", "retailer", 40.7831, -73.9712, 4000, 8, 22, "Metro City"),
    ("GreenGrocer Central", "retailer", 40.7488, -73.9856, 3500, 8, 21, "Metro City"),
    ("SuperSave East", "retailer", 40.7282, -73.7949, 6000, 7, 24, "Metro City"),
    ("FreshMart Valley", "retailer", 34.0522, -118.2437, 4500, 7, 22, "Green Valley"),
    ("Nature's Best", "retailer", 34.0195, -118.4912, 3800, 8, 21, "Green Valley"),
    ("Valley Organics", "retailer", 34.0689, -118.4452, 3000, 9, 20, "Green Valley"),
    ("Harbor Fresh", "retailer", 37.7749, -122.4194, 5000, 7, 23, "Harbor Town"),
    ("Seaside Market", "retailer", 37.8044, -122.2712, 4200, 8, 22, "Harbor Town"),
    ("Dock Street Grocery", "retailer", 37.7946, -122.3999, 3500, 8, 21, "Harbor Town"),
    # Food banks
    ("Metro Food Bank", "food_bank", 40.7549, -73.9840, 8000, 9, 18, "Metro City"),
    ("Valley Community Kitchen", "food_bank", 34.0407, -118.2468, 6000, 8, 17, "Green Valley"),
    ("Harbor Soup Kitchen", "food_bank", 37.7849, -122.4094, 5000, 9, 18, "Harbor Town"),
    # Compost/Biogas
    ("Metro Compost Hub", "compost_facility", 40.6892, -74.0445, 15000, 6, 20, "Metro City"),
    ("Valley Biogas Plant", "compost_facility", 34.0900, -118.3600, 12000, 6, 20, "Green Valley"),
]

# ── Supplier Definitions ─────────────────────────────────────
SUPPLIER_DEFS = [
    ("Valley Farms Co-op", 34.1000, -118.3000, 12, 0.92, 8000, "Green Valley"),
    ("Metro Produce Dist.", 40.7000, -74.0100, 6, 0.95, 10000, "Metro City"),
    ("Pacific Seafood Inc.", 37.7500, -122.4500, 8, 0.88, 5000, "Harbor Town"),
    ("Heartland Dairy", 40.8000, -73.9500, 8, 0.93, 7000, "Metro City"),
    ("Premium Meats Ltd.", 40.7200, -74.0000, 6, 0.90, 6000, "Metro City"),
    ("Sunrise Bakeries", 34.0600, -118.2500, 4, 0.96, 4000, "Green Valley"),
    ("Harbor Fish Market", 37.8000, -122.4000, 4, 0.91, 3000, "Harbor Town"),
    ("Green Fields Organic", 34.0800, -118.5000, 10, 0.89, 6000, "Green Valley"),
    ("National Dry Goods", 40.7400, -73.9900, 24, 0.97, 15000, "Metro City"),
    ("Frozen Foods Direct", 37.7600, -122.3800, 12, 0.94, 8000, "Harbor Town"),
    ("Snack Masters Inc.", 40.7300, -74.0200, 24, 0.96, 5000, "Metro City"),
    ("Fresh Deli Supplies", 34.0500, -118.2400, 6, 0.90, 3000, "Green Valley"),
    ("BioFarm Collective", 37.8200, -122.3000, 8, 0.87, 4000, "Harbor Town"),
    ("Tropical Imports Co.", 40.7100, -74.0300, 18, 0.85, 5000, "Metro City"),
    ("Golden Grain Mills", 34.0300, -118.2200, 48, 0.98, 12000, "Green Valley"),
    ("Regional Beverage Dist.", 37.7700, -122.4100, 12, 0.95, 6000, "Harbor Town"),
    ("Farm To Table Co.", 40.7600, -73.9700, 8, 0.91, 5000, "Metro City"),
    ("Coastal Produce", 37.7900, -122.4050, 10, 0.89, 5500, "Harbor Town"),
    ("Mountain Dairy Farm", 34.1200, -118.4800, 8, 0.92, 4000, "Green Valley"),
    ("Heritage Meat Packers", 40.7350, -73.9950, 6, 0.93, 4500, "Metro City"),
]

# Category-to-supplier mapping (which supplier indices serve which categories)
CATEGORY_SUPPLIERS = {
    "Fruits": [0, 1, 7, 12, 13, 16, 17],
    "Vegetables": [0, 1, 7, 12, 16, 17],
    "Dairy": [3, 18],
    "Meat": [4, 19],
    "Seafood": [2, 6, 17],
    "Bakery": [5],
    "Beverages": [15, 8],
    "Pantry": [8, 14, 10],
    "Frozen": [9],
    "Snacks": [10],
    "Deli": [11, 16],
    "Baby": [8],
}

# ── Event Definitions ────────────────────────────────────────
EVENT_TEMPLATES = [
    ("New Year's Day", "holiday", 1.5, "Beverages,Snacks,Meat"),
    ("Super Bowl Sunday", "sports", 1.8, "Snacks,Beverages,Frozen,Deli"),
    ("Valentine's Day", "holiday", 1.3, "Bakery,Snacks,Beverages"),
    ("St. Patrick's Day", "holiday", 1.2, "Beverages,Snacks"),
    ("Easter", "holiday", 1.4, "Bakery,Meat,Dairy,Vegetables"),
    ("Mother's Day", "holiday", 1.3, "Bakery,Fruits,Beverages"),
    ("Memorial Day BBQ", "holiday", 1.6, "Meat,Beverages,Bakery,Snacks"),
    ("Father's Day", "holiday", 1.2, "Meat,Beverages,Snacks"),
    ("Independence Day", "holiday", 1.7, "Meat,Beverages,Snacks,Bakery,Frozen"),
    ("Labor Day", "holiday", 1.5, "Meat,Beverages,Snacks"),
    ("Halloween", "holiday", 1.4, "Snacks,Bakery,Beverages"),
    ("Thanksgiving", "holiday", 2.0, "Meat,Vegetables,Bakery,Dairy,Fruits"),
    ("Christmas", "holiday", 1.8, "Meat,Bakery,Dairy,Beverages,Snacks,Fruits"),
    ("Local Food Festival", "local_event", 1.6, "Fruits,Vegetables,Deli,Bakery"),
    ("College Football Game", "sports", 1.4, "Snacks,Beverages,Frozen"),
    ("Marathon Weekend", "sports", 1.3, "Beverages,Fruits,Snacks"),
    ("Summer Concert Series", "local_event", 1.3, "Beverages,Snacks"),
    ("Farmers Market Week", "local_event", 1.5, "Fruits,Vegetables"),
    ("Back to School", "seasonal", 1.3, "Pantry,Snacks,Bakery,Dairy"),
    ("Spring Break", "seasonal", 1.2, "Snacks,Beverages,Frozen"),
    ("Heat Wave Alert", "weather_event", 1.5, "Beverages,Frozen,Fruits"),
    ("Cold Snap", "weather_event", 1.3, "Pantry,Dairy,Bakery"),
    ("Charity Food Drive", "local_event", 0.9, "Pantry,Canned"),
    ("Restaurant Week", "local_event", 0.85, "Meat,Seafood,Vegetables"),
    ("Neighborhood Block Party", "local_event", 1.4, "Snacks,Beverages,Bakery,Meat"),
]


def generate_weather_data():
    """Generate 2 years of daily weather data for each city."""
    weather_records = []
    for day_offset in range(NUM_DAYS):
        date = START_DATE + timedelta(days=day_offset)
        day_of_year = date.timetuple().tm_yday

        for city in CITIES:
            # Base temperature with seasonal pattern
            if city == "Metro City":
                base_temp = 12 + 15 * math.sin((day_of_year - 80) * 2 * math.pi / 365)
            elif city == "Green Valley":
                base_temp = 18 + 10 * math.sin((day_of_year - 80) * 2 * math.pi / 365)
            else:  # Harbor Town
                base_temp = 14 + 8 * math.sin((day_of_year - 80) * 2 * math.pi / 365)

            temp = base_temp + np.random.normal(0, 3)
            humidity = max(20, min(100, 55 + 20 * math.sin((day_of_year - 170) * 2 * math.pi / 365) + np.random.normal(0, 10)))
            precip = max(0, np.random.exponential(2) if random.random() < 0.3 else 0)
            wind = max(0, np.random.normal(15, 8))

            conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Rain", "Heavy Rain", "Storm", "Fog", "Snow"]
            if precip > 10:
                cond = random.choice(["Heavy Rain", "Storm"])
            elif precip > 2:
                cond = "Rain"
            elif temp < 0 and precip > 0:
                cond = "Snow"
            elif humidity > 85:
                cond = random.choice(["Fog", "Cloudy"])
            else:
                cond = random.choices(["Sunny", "Partly Cloudy", "Cloudy"], weights=[0.5, 0.3, 0.2])[0]

            weather_records.append((
                date.strftime("%Y-%m-%d"), city,
                round(temp, 1), round(humidity, 1),
                round(precip, 1), round(wind, 1), cond
            ))
    return weather_records


def generate_events():
    """Generate events across 2 years for all cities."""
    event_records = []
    fixed_dates_2025 = {
        "New Year's Day": "2025-01-01", "Super Bowl Sunday": "2025-02-09",
        "Valentine's Day": "2025-02-14", "St. Patrick's Day": "2025-03-17",
        "Easter": "2025-04-20", "Mother's Day": "2025-05-11",
        "Memorial Day BBQ": "2025-05-26", "Father's Day": "2025-06-15",
        "Independence Day": "2025-07-04", "Labor Day": "2025-09-01",
        "Halloween": "2025-10-31", "Thanksgiving": "2025-11-27",
        "Christmas": "2025-12-25",
    }

    for evt_name, evt_type, mult, cats in EVENT_TEMPLATES:
        if evt_name in fixed_dates_2025:
            for city in CITIES:
                event_records.append((
                    fixed_dates_2025[evt_name], evt_name, evt_type,
                    city, mult + np.random.normal(0, 0.05), cats
                ))
        else:
            # Random recurring events in 2025
            num_occurrences = random.randint(1, 3)
            for _ in range(num_occurrences):
                month = random.randint(1, 12)
                day = random.randint(1, 28)
                date_str = f"2025-{month:02d}-{day:02d}"
                city = random.choice(CITIES)
                event_records.append((
                    date_str, evt_name, evt_type,
                    city, mult + np.random.normal(0, 0.1), cats
                ))
    return event_records


def generate_sales_data(products_df, stores_df, weather_df, events_df):
    """Generate 100K+ sales records with realistic patterns."""
    print("  Generating sales data (this may take a moment)...")

    sales_records = []
    inventory_records = []
    event_lookup = {}
    for _, evt in events_df.iterrows():
        key = (evt["date"], evt["city"])
        if key not in event_lookup:
            event_lookup[key] = []
        event_lookup[key].append(evt)

    weather_lookup = {}
    for _, w in weather_df.iterrows():
        weather_lookup[(w["date"], w["city"])] = w

    retailer_stores = stores_df[stores_df["store_type"] == "retailer"]

    for day_offset in range(NUM_DAYS):
        date = START_DATE + timedelta(days=day_offset)
        date_str = date.strftime("%Y-%m-%d")
        dow = date.weekday()  # 0=Monday
        month = date.month
        day_of_year = date.timetuple().tm_yday

        for _, store in retailer_stores.iterrows():
            city = store["city"]
            store_id = store["store_id"]
            weather = weather_lookup.get((date_str, city))
            temp = weather["temp_c"] if weather is not None else 20
            events_today = event_lookup.get((date_str, city), [])

            # Sample a subset of products for this store/day (not every product sells daily)
            num_products = random.randint(30, min(80, len(products_df)))
            product_sample = products_df.sample(n=num_products, replace=False)

            for _, product in product_sample.iterrows():
                pid = product["product_id"]
                base_demand = product["avg_daily_demand"]
                category = product["category"]

                # ── Demand modifiers ──

                # 1. Day-of-week effect (weekends +20-40%)
                if dow >= 5:
                    dow_mult = 1.2 + random.uniform(0, 0.2)
                elif dow == 0:  # Monday dip
                    dow_mult = 0.85
                elif dow == 4:  # Friday bump
                    dow_mult = 1.1
                else:
                    dow_mult = 1.0

                # 2. Seasonal effect
                if category in ["Fruits", "Beverages", "Frozen"]:
                    seasonal = 1 + 0.3 * math.sin((day_of_year - 80) * 2 * math.pi / 365)
                elif category in ["Pantry", "Bakery", "Dairy"]:
                    seasonal = 1 + 0.15 * math.sin((day_of_year - 260) * 2 * math.pi / 365)
                elif category == "Meat":
                    seasonal = 1 + 0.2 * math.sin((day_of_year - 150) * 2 * math.pi / 365)
                else:
                    seasonal = 1.0

                # 3. Weather effect
                if temp > 30 and category in ["Beverages", "Frozen", "Fruits"]:
                    weather_mult = 1.3
                elif temp < 5 and category in ["Pantry", "Bakery", "Dairy"]:
                    weather_mult = 1.2
                elif weather is not None and weather["condition"] in ["Storm", "Heavy Rain"]:
                    weather_mult = 0.7  # bad weather = fewer customers
                else:
                    weather_mult = 1.0

                # 4. Event effect
                event_mult = 1.0
                event_flag = 0
                for evt in events_today:
                    affected = evt["affected_categories"].split(",")
                    if category in affected:
                        event_mult = max(event_mult, evt["impact_multiplier"])
                        event_flag = 1

                # 5. Store size effect
                store_scale = store["capacity_kg"] / 5000

                # 6. Random noise
                noise = max(0.3, np.random.normal(1, 0.15))

                # ── Calculate quantities ──
                demand = base_demand * dow_mult * seasonal * weather_mult * event_mult * store_scale * noise
                demand = max(1, demand)

                # Order quantity (slightly over demand to account for uncertainty)
                order_buffer = 1.0 + random.uniform(0.05, 0.25)
                qty_ordered = round(demand * order_buffer, 1)

                # Actual sold (usually close to demand, sometimes less)
                qty_sold = round(min(qty_ordered, demand * max(0.7, np.random.normal(1, 0.08))), 1)
                qty_sold = max(0, qty_sold)

                # Waste = ordered - sold (only for perishables mainly)
                if product["is_perishable"]:
                    qty_wasted = round(max(0, qty_ordered - qty_sold), 1)
                else:
                    qty_wasted = round(max(0, (qty_ordered - qty_sold) * random.uniform(0, 0.1)), 1)

                revenue = round(qty_sold * product["unit_price"], 2)
                waste_cost = round(qty_wasted * product["unit_cost"], 2)

                sales_records.append((
                    date_str, store_id, pid,
                    qty_ordered, qty_sold, qty_wasted,
                    revenue, waste_cost, round(temp, 1),
                    event_flag, dow, month
                ))

                # ── Inventory snapshot ──
                days_until_expiry = max(0, product["shelf_life_days"] - random.randint(0, product["shelf_life_days"]))
                freshness = round(days_until_expiry / max(1, product["shelf_life_days"]), 2)
                on_hand = round(max(0, qty_ordered - qty_sold + random.uniform(0, base_demand * 0.3)), 1)

                inventory_records.append((
                    date_str, store_id, pid,
                    on_hand, days_until_expiry, freshness
                ))

    return sales_records, inventory_records


def seed_database(seed: int = DEFAULT_SEED):
    """Main function to seed all data into the database."""
    set_random_seed(seed)
    print("🌱 FoodFlow AI — Seeding Database")
    print("=" * 50)
    print(f"🎲 Using random seed: {seed}")

    reset_database()

    with get_db() as conn:

        # ── 1. Products ──
        print("📦 Inserting products...")
        for p in PRODUCT_DEFS:
            conn.execute("""
                INSERT INTO products (name, category, subcategory, shelf_life_days,
                    avg_daily_demand, unit_cost, unit_price, carbon_footprint_kg,
                    storage_temp_min, storage_temp_max, is_perishable)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """, (p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7],
                  2 if p[8] else -18, 8 if p[8] else -10, p[8]))
        print(f"  ✅ {len(PRODUCT_DEFS)} products inserted")

        # ── 2. Stores ──
        print("🏪 Inserting stores...")
        for s in STORE_DEFS:
            conn.execute("""
                INSERT INTO stores (name, store_type, latitude, longitude,
                    capacity_kg, operating_hours_start, operating_hours_end, city)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, s)
        print(f"  ✅ {len(STORE_DEFS)} stores inserted")

        # ── 3. Suppliers ──
        print("🚛 Inserting suppliers...")
        for s in SUPPLIER_DEFS:
            conn.execute("""
                INSERT INTO suppliers (name, latitude, longitude, lead_time_hours,
                    reliability_score, capacity_kg_per_day, city)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, s)
        print(f"  ✅ {len(SUPPLIER_DEFS)} suppliers inserted")

        # ── 4. Supplier-Product Mapping ──
        print("🔗 Mapping suppliers to products...")
        products_df = conn.execute("SELECT * FROM products").fetchdf()
        sp_count = 0
        for _, prod in products_df.iterrows():
            cat = prod["category"]
            supplier_indices = CATEGORY_SUPPLIERS.get(cat, [8])
            for si in supplier_indices:
                if si < len(SUPPLIER_DEFS):
                    try:
                        conn.execute("""
                            INSERT INTO supplier_products (supplier_id, product_id, unit_cost, min_order_qty)
                            VALUES ($1, $2, $3, $4)
                        """, (si + 1, int(prod["product_id"]), prod["unit_cost"] * 0.85, 10))
                        sp_count += 1
                    except Exception:
                        pass  # skip duplicates
        print(f"  ✅ {sp_count} supplier-product mappings created")

        # ── 5. Weather ──
        print("🌤️ Generating weather data...")
        weather_records = generate_weather_data()
        weather_df = pd.DataFrame(weather_records,
            columns=["date", "city", "temp_c", "humidity", "precipitation_mm", "wind_speed_kmh", "condition"])
        conn.execute("INSERT INTO weather (date, city, temp_c, humidity, precipitation_mm, wind_speed_kmh, condition) SELECT * FROM weather_df")
        print(f"  ✅ {len(weather_records)} weather records inserted")

        # ── 6. Events ──
        print("🎉 Generating events...")
        event_records = generate_events()
        events_df = pd.DataFrame(event_records,
            columns=["date", "event_name", "event_type", "city", "impact_multiplier", "affected_categories"])
        conn.execute("INSERT INTO events (date, event_name, event_type, city, impact_multiplier, affected_categories) SELECT * FROM events_df")
        print(f"  ✅ {len(event_records)} events inserted")

        # ── 7. Sales & Inventory ──
        print("🧾 Generating sales & inventory data...")
        products_df = conn.execute("SELECT * FROM products").fetchdf()
        stores_df = conn.execute("SELECT * FROM stores").fetchdf()
        weather_df = conn.execute("SELECT * FROM weather").fetchdf()
        events_df2 = conn.execute("SELECT * FROM events").fetchdf()

        sales_records, inventory_records = generate_sales_data(
            products_df, stores_df, weather_df, events_df2
        )

        print(f"  Inserting {len(sales_records)} sales records...")
        sales_df = pd.DataFrame(sales_records,
            columns=["date", "store_id", "product_id", "qty_ordered", "qty_sold",
                     "qty_wasted", "revenue", "waste_cost", "weather_temp",
                     "event_flag", "day_of_week", "month"])
        conn.execute("INSERT INTO sales (date, store_id, product_id, qty_ordered, qty_sold, qty_wasted, revenue, waste_cost, weather_temp, event_flag, day_of_week, month) SELECT * FROM sales_df")
        print(f"  ✅ {len(sales_records)} sales records inserted")

        # Inventory — last 30 days
        recent_inv = [r for r in inventory_records
                      if r[0] >= (END_DATE - timedelta(days=30)).strftime("%Y-%m-%d")]
        inv_df = pd.DataFrame(recent_inv,
            columns=["date", "store_id", "product_id", "quantity_on_hand",
                     "days_until_expiry", "freshness_score"])
        conn.execute("INSERT INTO inventory (date, store_id, product_id, quantity_on_hand, days_until_expiry, freshness_score) SELECT * FROM inv_df ON CONFLICT (date, store_id, product_id) DO UPDATE SET quantity_on_hand = EXCLUDED.quantity_on_hand, days_until_expiry = EXCLUDED.days_until_expiry, freshness_score = EXCLUDED.freshness_score")
        print(f"  ✅ {len(recent_inv)} inventory snapshots inserted")

    # ── Summary ──
    print("\n" + "=" * 50)
    print("🎉 DATABASE SEEDING COMPLETE!")
    print("=" * 50)
    with get_db() as conn:
        for table in ["products", "stores", "suppliers", "weather", "events", "sales", "inventory"]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  📊 {table}: {count:,} records")
    print(f"\n  💾 Database location: {os.path.abspath(os.path.join(os.path.dirname(__file__), 'foodflow.duckdb'))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed FoodFlow DuckDB database with synthetic data.")
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for dataset generation (default: {DEFAULT_SEED})",
    )
    args = parser.parse_args()
    seed_database(seed=args.seed)
