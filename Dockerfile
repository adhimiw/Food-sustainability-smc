# /home/adhithan/.openclaw/workspace/Food-sustainability-smc/Dockerfile
FROM astral-sh/uv:python3.12-bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml requirements.txt uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen

# Copy the rest of the application
COPY . .

# Ensure the database directory exists
RUN mkdir -p data

# Expose ports for Streamlit (8501) and FastAPI (8000)
EXPOSE 8501 8000

# Entrypoint script to handle seeding and startup
COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
