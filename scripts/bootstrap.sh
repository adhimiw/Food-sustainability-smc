#!/bin/bash
# scripts/bootstrap.sh

echo "🛠️ Starting FoodFlow AI Setup..."

# 1. Install uv
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# 2. Check Docker
if ! command -v docker &> /dev/null; then
    echo "⚠️ Warning: Docker not found. Please install Docker Desktop for Windows."
fi

# 3. Create .env from example if missing
if [ ! -f ".env" ]; then
    echo "📄 Creating .env file..."
    cp .env.example .env
    echo "⚠️ Action Required: Please update MISTRAL_API_KEY in the .env file."
fi

# 4. Create plugins directory for Metabase
mkdir -p metabase-plugins
if [ ! -f "metabase-plugins/duckdb.metabase-driver.jar" ]; then
    echo "📥 Downloading DuckDB Metabase driver..."
    curl -L -o metabase-plugins/duckdb.metabase-driver.jar https://github.com/evilsagittarius/metabase-duckdb-driver/releases/download/v1.4.3.1/duckdb.metabase-driver.jar
fi

# 5. Build and Launch
echo "🏗️ Building Docker containers..."
docker-compose build
echo "🚀 Launching stack..."
docker-compose up -d

echo "✅ Setup complete!"
echo "📍 Dashboard: http://localhost:8501"
echo "📍 Metabase: http://localhost:3000"
