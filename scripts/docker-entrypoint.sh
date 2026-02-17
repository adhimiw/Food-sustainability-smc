#!/bin/bash
# scripts/docker-entrypoint.sh

# Seed database if it doesn't exist
if [ ! -f "data/foodflow.duckdb" ]; then
    echo "🌱 Seeding database..."
    uv run python data/seed_database.py
fi

# Run the app (Streamlit by default)
echo "🚀 Starting FoodFlow AI..."
uv run streamlit run app.py --server.port 8501 --server.address 0.0.0.0
