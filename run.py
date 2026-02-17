"""
FoodFlow AI — One-Click Launcher
Seeds the database, trains the model, runs the cascade, and launches the dashboard.
"""

import sys
import os
import subprocess
import time

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def print_banner():
    banner = """
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║   🌿  FoodFlow AI — Food Waste Reduction Platform  🌿   ║
    ║                                                          ║
    ║   Demand Prediction • Distribution Optimization          ║
    ║   Waste Cascade • Carbon Impact Tracking                 ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """
    print(banner)


def step(num, total, msg):
    print(f"\n{'='*60}")
    print(f"  Step {num}/{total}: {msg}")
    print(f"{'='*60}")


def main():
    print_banner()
    total_steps = 5
    start_time = time.time()

    skip_seed = "--skip-seed" in sys.argv

    # ── Step 1: Initialize & Seed Database ──
    db_path = os.path.join(PROJECT_ROOT, "data", "foodflow.duckdb")
    if skip_seed and os.path.exists(db_path):
        step(1, total_steps, "Skipping DB Seed (--skip-seed, DB exists)")
        print("  Using existing database.")
    else:
        step(1, total_steps, "Seeding Database with Synthetic Data")
        from data.seed_database import seed_database
        seed_database()

    # ── Step 2: Train Demand Forecaster ──
    step(2, total_steps, "Training AI Demand Forecaster")
    from models.demand_forecaster import DemandForecaster
    forecaster = DemandForecaster()
    metrics = forecaster.train(days_back=365, verbose=True)
    print(f"\n  Model Performance: MAE={metrics['mae']:.2f}, MAPE={metrics['mape']:.1f}%")

    # ── Step 3: Run Waste Cascade Optimization ──
    step(3, total_steps, "Running Waste Cascade Optimization")
    from models.waste_cascade import WasteCascadeOptimizer
    cascade = WasteCascadeOptimizer()
    cascade.load_data()
    cascade.identify_surplus(forecast_days=3)
    actions = cascade.optimize_cascade()
    cascade.save_actions()
    print(f"  Generated {len(actions)} redistribution actions")

    # ── Step 4: Optimize Routes ──
    step(4, total_steps, "Optimizing Delivery Routes")
    from models.route_optimizer import RouteOptimizer
    router = RouteOptimizer()
    routes = router.optimize_routes(num_vehicles=3)
    router.save_routes()
    print(f"  Optimized {len(routes)} delivery routes")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  ✅ All models trained and data generated in {elapsed:.1f}s")
    print(f"{'='*60}")

    # ── Step 5: Launch Dashboard ──
    step(5, total_steps, "Launching Unified Streamlit App")
    print("\n  🌐 App will open at:         http://localhost:8501")
    print("  📊 Dashboard:                http://localhost:8501 (page 1)")
    print("  🤖 AI Chatbot:               http://localhost:8501 (page 2)")
    print("  🧠 Agentic Dashboard:        http://localhost:8501 (page 3)")
    print("  📡 API available at:         http://localhost:8000/docs")
    print("\n  Press Ctrl+C to stop.\n")

    # Start FastAPI in background
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Start Streamlit unified app (foreground)
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run",
             "app.py",
             "--server.port", "8501",
             "--server.headless", "true",
             "--browser.gatherUsageStats", "false"],
            cwd=PROJECT_ROOT
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    finally:
        api_proc.terminate()
        print("👋 FoodFlow AI stopped. Goodbye!")


if __name__ == "__main__":
    main()
