"""
FoodFlow AI — Streamlit Dashboard
Interactive analytics dashboard for food waste reduction platform.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta

from database.db import get_db, init_database
from utils.helpers import (
    get_sales_dataframe, get_products_dataframe, get_stores_dataframe,
    get_waste_summary, get_daily_waste_trend, get_inventory_dataframe,
    format_currency, format_weight, format_co2
)
from models.carbon_calculator import (
    get_carbon_summary, get_equivalencies, CARBON_FACTORS
)

# ══════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="FoodFlow AI — Food Waste Reduction Platform",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ──
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1B5E20;
        text-align: center;
        padding: 0.5rem 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        border-left: 4px solid #2E7D32;
    }
    .alert-card {
        background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%);
        border-radius: 12px;
        padding: 1rem;
        border-left: 4px solid #EF6C00;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a3a2a 0%, #1e4d35 100%);
        border: 1px solid #2E7D32;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    [data-testid="stMetric"] label {
        color: #A5D6A7 !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: #81C784 !important;
    }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1B5E20 0%, #2E7D32 50%, #388E3C 100%);
    }
    div[data-testid="stSidebar"] .stMarkdown {
        color: white;
    }
    div[data-testid="stSidebar"] label {
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("# 🌿 FoodFlow AI")
    st.markdown("*Waste Less. Feed More. Save Earth.*")
    st.markdown("---")

    page = st.radio(
        "Navigate",
        ["📊 Overview Dashboard",
         "🔮 Demand Forecast",
         "♻️ Waste Cascade",
         "🗺️ Route Optimizer",
         "🌍 Carbon Impact",
         "📈 Analytics"],
        index=0
    )

    st.markdown("---")
    st.markdown("### ⚙️ Settings")

    # Date filter
    import datetime as dt
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date = st.date_input("Start Date", value=dt.date(2025, 1, 1), min_value=dt.date(2025, 1, 1), max_value=dt.date(2025, 12, 31))
    with date_col2:
        end_date = st.date_input("End Date", value=dt.date(2025, 12, 31), min_value=dt.date(2025, 1, 1), max_value=dt.date(2025, 12, 31))

    date_filter_sql = f"AND s.date >= '{start_date}' AND s.date <= '{end_date}'"
    date_filter_plain = f"AND date >= '{start_date}' AND date <= '{end_date}'"

    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    try:
        waste = get_waste_summary()
        total_waste = waste.get("total_waste_kg", 0) or 0
        total_sold = waste.get("total_sold_kg", 0) or 0
        rate = (total_waste / (total_sold + total_waste) * 100) if (total_sold + total_waste) > 0 else 0
        st.metric("Total Records", f"{waste.get('num_days', 0) or 0:,} days")
        st.metric("Waste Rate", f"{rate:.1f}%")
    except Exception:
        st.info("Seed database first")

    st.markdown("---")
    st.caption("Built for Hackathon 2026")


# ══════════════════════════════════════════════════════════════
#  PAGE: OVERVIEW DASHBOARD
# ══════════════════════════════════════════════════════════════

def page_overview():
    st.markdown('<div class="main-header">🌿 FoodFlow AI Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">AI-Powered Food Waste Reduction • Demand Prediction • Distribution Optimization</div>', unsafe_allow_html=True)

    try:
        waste = get_waste_summary()
    except Exception:
        st.error("Database not initialized. Please run the data seeder first.")
        st.code("cd foodflow-ai && python data/seed_database.py", language="bash")
        return

    total_waste = waste.get("total_waste_kg", 0) or 0
    total_sold = waste.get("total_sold_kg", 0) or 0
    total_revenue = waste.get("total_revenue", 0) or 0
    total_waste_cost = waste.get("total_waste_cost", 0) or 0
    waste_rate = (total_waste / (total_sold + total_waste) * 100) if (total_sold + total_waste) > 0 else 0

    # ── KPI Row ──
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📦 Total Sold", format_weight(total_sold))
    with col2:
        st.metric("🗑️ Total Waste", format_weight(total_waste), delta=f"-{waste_rate:.1f}% rate")
    with col3:
        st.metric("💰 Revenue", format_currency(total_revenue))
    with col4:
        st.metric("💸 Waste Cost", format_currency(total_waste_cost), delta="negative", delta_color="inverse")
    with col5:
        potential = total_waste_cost * 0.30
        st.metric("🎯 AI Savings Target", format_currency(potential), delta="30% reduction")

    st.markdown("---")

    # ── AI Impact Projection ──
    st.subheader("🤖 AI Impact Projection")
    ai_col1, ai_col2, ai_col3, ai_col4 = st.columns(4)

    carbon = get_carbon_summary()
    co2_total = carbon.get("total_waste_co2_kg", 0)
    co2_savings = co2_total * 0.30
    equivalencies = get_equivalencies(co2_savings)

    with ai_col1:
        st.metric("🌳 Trees Equivalent", f"{equivalencies['trees_planted']:,.0f}", help="Trees needed to absorb same CO₂")
    with ai_col2:
        st.metric("🚗 Car KM Avoided", f"{equivalencies['car_km_avoided']:,.0f}")
    with ai_col3:
        st.metric("✈️ Flights Saved", f"{equivalencies['flights_avoided']:.1f}")
    with ai_col4:
        st.metric("📱 Phone Charges", f"{equivalencies['smartphones_charged']:,.0f}")

    st.markdown("---")

    # ── Charts Row ──
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("📉 Daily Waste Trend")
        trend_df = get_daily_waste_trend()
        # Apply date filter
        trend_df = trend_df[(trend_df["date"] >= pd.Timestamp(start_date)) & (trend_df["date"] <= pd.Timestamp(end_date))]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["total_waste"],
            mode="lines", name="Waste (kg)",
            line=dict(color="#d32f2f", width=2),
            fill="tozeroy", fillcolor="rgba(211,47,47,0.1)"
        ))
        fig.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["total_waste"].rolling(7).mean(),
            mode="lines", name="7-day Average",
            line=dict(color="#ff9800", width=2, dash="dash")
        ))
        fig.update_layout(
            height=350, margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            xaxis_title="", yaxis_title="Waste (kg)"
        )
        st.plotly_chart(fig, width='stretch')

    with chart_col2:
        st.subheader("📊 Waste by Category")
        with get_db() as conn:
            cat_df = conn.execute(f"""
                SELECT p.category, SUM(s.qty_wasted) as waste_kg
                FROM sales s JOIN products p ON s.product_id = p.product_id
                WHERE 1=1 {date_filter_sql}
                GROUP BY p.category ORDER BY waste_kg DESC
            """).fetchdf()
        fig = px.pie(cat_df, values="waste_kg", names="category",
                     color_discrete_sequence=px.colors.qualitative.Set3,
                     hole=0.4)
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20))
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, width='stretch')

    # ── Bottom Row ──
    bot_col1, bot_col2 = st.columns(2)

    with bot_col1:
        st.subheader("🏪 Store Performance")
        with get_db() as conn:
            store_df = conn.execute(f"""
                SELECT st.name, st.city,
                       SUM(s.qty_wasted) as waste_kg,
                       ROUND(SUM(s.qty_wasted)*100.0/NULLIF(SUM(s.qty_ordered),0), 1) as waste_rate
                FROM sales s JOIN stores st ON s.store_id = st.store_id
                WHERE st.store_type = 'retailer' {date_filter_sql}
                GROUP BY st.store_id, st.name, st.city ORDER BY waste_rate ASC
            """).fetchdf()
        fig = px.bar(store_df, x="waste_rate", y="name", orientation="h",
                     color="waste_rate", color_continuous_scale="RdYlGn_r",
                     labels={"waste_rate": "Waste Rate %", "name": ""})
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=10, b=20),
                          showlegend=False, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, width='stretch')

    with bot_col2:
        st.subheader("⚠️ Top Wasted Products")
        with get_db() as conn:
            top_waste = conn.execute(f"""
                SELECT p.name, p.category, p.shelf_life_days,
                       SUM(s.qty_wasted) as waste_kg,
                       SUM(s.waste_cost) as waste_cost
                FROM sales s JOIN products p ON s.product_id = p.product_id
                WHERE 1=1 {date_filter_sql}
                GROUP BY p.product_id, p.name, p.category, p.shelf_life_days ORDER BY waste_kg DESC LIMIT 10
            """).fetchdf()
        fig = px.bar(top_waste, x="waste_kg", y="name", orientation="h",
                     color="category",
                     labels={"waste_kg": "Total Waste (kg)", "name": ""})
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=10, b=20),
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, width='stretch')


# ══════════════════════════════════════════════════════════════
#  PAGE: DEMAND FORECAST
# ══════════════════════════════════════════════════════════════

def page_forecast():
    st.markdown("## 🔮 Demand Forecast Engine")
    st.markdown("AI-powered demand prediction using XGBoost with 30+ engineered features")

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        stores = get_stores_dataframe("retailer")
        store_options = {f"{r['name']} ({r['city']})": r["store_id"] for _, r in stores.iterrows()}
        selected_store = st.selectbox("Select Store", list(store_options.keys()))
        store_id = store_options[selected_store]

    with col2:
        products = get_products_dataframe()
        cat_filter = st.selectbox("Category Filter", ["All"] + sorted(products["category"].unique().tolist()))
        if cat_filter != "All":
            products = products[products["category"] == cat_filter]
        prod_options = {r["name"]: r["product_id"] for _, r in products.iterrows()}
        selected_prod = st.selectbox("Select Product", list(prod_options.keys()))
        product_id = prod_options[selected_prod]

    with col3:
        days_ahead = st.slider("Forecast Days", 3, 14, 7)
        train_btn = st.button("🚀 Train & Predict", type="primary", width='stretch')

    if train_btn:
        with st.spinner("Training AI model... This may take a moment."):
            try:
                from models.demand_forecaster import DemandForecaster
                forecaster = DemandForecaster()
                metrics = forecaster.train(days_back=365, verbose=False)

                met_col1, met_col2, met_col3, met_col4 = st.columns(4)
                with met_col1:
                    st.metric("Model", metrics.get("model", "XGBoost"))
                with met_col2:
                    st.metric("MAE", f"{metrics.get('mae', 0):.2f}")
                with met_col3:
                    st.metric("MAPE", f"{metrics.get('mape', 0):.1f}%")
                with met_col4:
                    st.metric("Train Size", f"{metrics.get('train_size', 0):,}")

                st.markdown("---")

                # Generate predictions
                preds = forecaster.predict(store_id, product_id, days_ahead, verbose=False)

                # Plot forecast
                st.subheader(f"📈 {days_ahead}-Day Forecast: {selected_prod}")

                # Get historical data for context
                hist = get_sales_dataframe(store_id=store_id, product_id=product_id, days_back=60)
                hist_daily = hist.groupby("date")["qty_sold"].sum().reset_index()

                fig = go.Figure()

                # Historical
                fig.add_trace(go.Scatter(
                    x=hist_daily["date"], y=hist_daily["qty_sold"],
                    mode="lines+markers", name="Historical Sales",
                    line=dict(color="#1976D2", width=2),
                    marker=dict(size=4)
                ))

                # Forecast
                forecast_dates = pd.to_datetime(preds["forecast_date"])
                fig.add_trace(go.Scatter(
                    x=forecast_dates, y=preds["predicted_demand"],
                    mode="lines+markers", name="Predicted Demand",
                    line=dict(color="#388E3C", width=3),
                    marker=dict(size=8, symbol="star")
                ))

                # Confidence band
                fig.add_trace(go.Scatter(
                    x=pd.concat([forecast_dates, forecast_dates[::-1]]),
                    y=pd.concat([preds["upper_bound"], preds["lower_bound"][::-1]]),
                    fill="toself", fillcolor="rgba(56,142,60,0.15)",
                    line=dict(color="rgba(56,142,60,0)"),
                    name="95% Confidence"
                ))

                fig.update_layout(
                    height=450,
                    xaxis_title="Date", yaxis_title="Quantity",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    margin=dict(l=20, r=20, t=50, b=20)
                )
                st.plotly_chart(fig, width='stretch')

                # Forecast table
                st.subheader("📋 Detailed Forecast")
                display_df = preds.copy()
                display_df.columns = ["Date", "Predicted Demand", "Lower Bound", "Upper Bound", "Confidence %", "Model"]
                st.dataframe(display_df, width='stretch', hide_index=True)

                # Feature importance
                if hasattr(forecaster, "feature_importance") and forecaster.feature_importance:
                    st.subheader("🔑 Top Feature Importance")
                    fi = forecaster.feature_importance
                    fi_df = pd.DataFrame({"Feature": list(fi.keys()), "Importance": list(fi.values())})
                    fi_df = fi_df.sort_values("Importance", ascending=True)
                    fig = px.bar(fi_df, x="Importance", y="Feature", orientation="h",
                                 color="Importance", color_continuous_scale="Greens")
                    fig.update_layout(height=400, margin=dict(l=20, r=20, t=10, b=20), showlegend=False)
                    st.plotly_chart(fig, width='stretch')

            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        st.info("👆 Select a store and product, then click **Train & Predict** to generate forecasts.")

        # Show historical overview
        st.subheader("📊 Historical Sales Overview")
        with get_db() as conn:
            overview = conn.execute(f"""
                SELECT date, SUM(qty_sold) as sold, SUM(qty_wasted) as wasted
                FROM sales WHERE 1=1 {date_filter_plain.replace('AND date', 'AND sales.date') if False else date_filter_plain}
                GROUP BY date ORDER BY date
            """).fetchdf()
        overview["date"] = pd.to_datetime(overview["date"])
        overview = overview[(overview["date"] >= pd.Timestamp(start_date)) & (overview["date"] <= pd.Timestamp(end_date))]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=overview["date"], y=overview["sold"], name="Sold",
                             marker_color="#4CAF50", opacity=0.7), secondary_y=False)
        fig.add_trace(go.Scatter(x=overview["date"], y=overview["wasted"], name="Wasted",
                                  line=dict(color="#F44336", width=2)), secondary_y=True)
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=30, b=20),
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        fig.update_yaxes(title_text="Sold (kg)", secondary_y=False)
        fig.update_yaxes(title_text="Wasted (kg)", secondary_y=True)
        st.plotly_chart(fig, width='stretch')


# ══════════════════════════════════════════════════════════════
#  PAGE: WASTE CASCADE
# ══════════════════════════════════════════════════════════════

def page_cascade():
    st.markdown("## ♻️ Waste Cascade Optimizer")
    st.markdown("3-tier redistribution: **Retailer → Food Bank → Composting** — Zero landfill")

    # Tier explanation
    tier_col1, tier_col2, tier_col3 = st.columns(3)
    with tier_col1:
        st.markdown("""
        <div style="background:#E3F2FD;padding:1rem;border-radius:10px;border-left:4px solid #1565C0;">
        <h4>🏪 Tier 1: Retailer Redistribution</h4>
        <p>Surplus moves to nearby stores with higher demand</p>
        </div>
        """, unsafe_allow_html=True)
    with tier_col2:
        st.markdown("""
        <div style="background:#E8F5E9;padding:1rem;border-radius:10px;border-left:4px solid #2E7D32;">
        <h4>🍲 Tier 2: Food Banks</h4>
        <p>Remaining edible food goes to community kitchens</p>
        </div>
        """, unsafe_allow_html=True)
    with tier_col3:
        st.markdown("""
        <div style="background:#FFF3E0;padding:1rem;border-radius:10px;border-left:4px solid #EF6C00;">
        <h4>🌱 Tier 3: Composting</h4>
        <p>Non-edible waste → biogas & compost. Zero landfill.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    if st.button("🔄 Run Cascade Optimization", type="primary", width='stretch'):
        with st.spinner("Analyzing surplus inventory and optimizing redistribution..."):
            try:
                from models.waste_cascade import WasteCascadeOptimizer
                optimizer = WasteCascadeOptimizer()
                optimizer.load_data()
                surplus = optimizer.identify_surplus(forecast_days=3)
                actions = optimizer.optimize_cascade()
                optimizer.save_actions()

                summary = optimizer.summary

                # Summary metrics
                s_col1, s_col2, s_col3, s_col4, s_col5 = st.columns(5)
                with s_col1:
                    st.metric("Total Actions", summary.get("total_actions", 0))
                with s_col2:
                    st.metric("Tier 1 (Retail)", format_weight(summary.get("tier_1_kg", 0)))
                with s_col3:
                    st.metric("Tier 2 (Food Bank)", format_weight(summary.get("tier_2_kg", 0)))
                with s_col4:
                    st.metric("Tier 3 (Compost)", format_weight(summary.get("tier_3_kg", 0)))
                with s_col5:
                    st.metric("CO₂ Saved", format_co2(summary.get("total_carbon_saved_kg", 0)))

                st.markdown("---")

                # Sankey Diagram
                if actions:
                    st.subheader("🔀 Food Flow — Sankey Diagram")
                    sankey = optimizer.get_sankey_data()

                    if sankey["nodes"] and sankey["links"]:
                        fig = go.Figure(data=[go.Sankey(
                            node=dict(
                                pad=15, thickness=20, line=dict(color="black", width=0.5),
                                label=[n["name"] for n in sankey["nodes"]],
                                color=["#42A5F5" if "Fresh" in n["name"] or "Green" in n["name"] or "Super" in n["name"]
                                       or "Nature" in n["name"] or "Valley" in n["name"] or "Harbor" in n["name"]
                                       or "Seaside" in n["name"] or "Dock" in n["name"]
                                       else "#66BB6A" if "Bank" in n["name"] or "Kitchen" in n["name"]
                                       else "#FFA726"
                                       for n in sankey["nodes"]]
                            ),
                            link=dict(
                                source=[l["source"] for l in sankey["links"]],
                                target=[l["target"] for l in sankey["links"]],
                                value=[l["value"] for l in sankey["links"]],
                                color=[l["color"] for l in sankey["links"]]
                            )
                        )])
                        fig.update_layout(height=500, margin=dict(l=20, r=20, t=30, b=20),
                                          font_size=11)
                        st.plotly_chart(fig, width='stretch')

                    # Actions table
                    st.subheader("📋 Redistribution Actions")
                    actions_df = pd.DataFrame(actions[:50])
                    if len(actions_df) > 0:
                        display_cols = ["cascade_tier", "source_name", "destination_name",
                                        "product_name", "category", "quantity_kg",
                                        "carbon_saved_kg", "cost_saved", "distance_km"]
                        available_cols = [c for c in display_cols if c in actions_df.columns]
                        st.dataframe(actions_df[available_cols], width='stretch', hide_index=True)

            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        # Show existing cascade data
        st.info("👆 Click **Run Cascade Optimization** to analyze current surplus and generate redistribution plan.")

        try:
            with get_db() as conn:
                existing = conn.execute("""
                    SELECT cascade_tier, COUNT(*) as actions,
                           SUM(quantity_kg) as total_kg,
                           SUM(carbon_saved_kg) as co2_saved,
                           SUM(cost_saved) as cost_saved
                    FROM waste_cascade_actions
                    GROUP BY cascade_tier
                """).fetchdf()
            if len(existing) > 0:
                st.subheader("📊 Previous Cascade Results")
                existing["tier_name"] = existing["cascade_tier"].map({
                    1: "🏪 Retailer", 2: "🍲 Food Bank", 3: "🌱 Compost"
                })
                fig = px.bar(existing, x="tier_name", y="total_kg",
                             color="tier_name", text="total_kg",
                             labels={"total_kg": "Quantity (kg)", "tier_name": "Tier"})
                fig.update_layout(height=350, showlegend=False)
                fig.update_traces(texttemplate="%{text:.0f} kg", textposition="outside")
                st.plotly_chart(fig, width='stretch')
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  PAGE: ROUTE OPTIMIZER
# ══════════════════════════════════════════════════════════════

def page_routes():
    st.markdown("## 🗺️ Route Optimization")
    st.markdown("Optimized delivery routes for food redistribution — minimizing distance & carbon emissions")

    r_col1, r_col2 = st.columns([1, 1])
    with r_col1:
        city_filter = st.selectbox("City", ["All", "Metro City", "Green Valley", "Harbor Town"])
        city = None if city_filter == "All" else city_filter
    with r_col2:
        num_vehicles = st.slider("Number of Vehicles", 1, 6, 3)

    if st.button("🚛 Optimize Routes", type="primary", width='stretch'):
        with st.spinner("Solving vehicle routing problem..."):
            try:
                from models.route_optimizer import RouteOptimizer
                optimizer = RouteOptimizer()
                routes = optimizer.optimize_routes(city=city, num_vehicles=num_vehicles)
                optimizer.save_routes()

                if routes:
                    summary = optimizer.summary

                    # Summary metrics
                    m1, m2, m3, m4, m5 = st.columns(5)
                    with m1:
                        st.metric("Routes", summary.get("num_routes", 0))
                    with m2:
                        st.metric("Total Distance", f"{summary.get('total_distance_km', 0):,.1f} km")
                    with m3:
                        st.metric("Total Time", f"{summary.get('total_time_minutes', 0):,.0f} min")
                    with m4:
                        st.metric("Total Load", format_weight(summary.get("total_load_kg", 0)))
                    with m5:
                        st.metric("CO₂ Emissions", format_co2(summary.get("total_co2_kg", 0)))

                    st.markdown("---")

                    # Map
                    st.subheader("🗺️ Route Map")
                    try:
                        import folium
                        from streamlit_folium import st_folium

                        map_data = optimizer.get_route_map_data()
                        if map_data:
                            first_coord = map_data[0]["coordinates"][0]
                            m = folium.Map(location=first_coord, zoom_start=11, tiles="CartoDB positron")

                            colors_list = ["blue", "red", "green", "purple", "orange", "darkred"]
                            for i, route in enumerate(map_data):
                                color = colors_list[i % len(colors_list)]
                                coords = route["coordinates"]

                                # Draw route line
                                folium.PolyLine(
                                    coords, weight=4, color=color, opacity=0.8,
                                    tooltip=f"Vehicle {route['vehicle_id']}: {route['distance_km']}km"
                                ).add_to(m)

                                # Add stop markers
                                for j, stop in enumerate(route["stops"]):
                                    icon_color = "green" if j == 0 else color
                                    icon_type = "home" if stop.get("is_depot") else "info-sign"
                                    folium.Marker(
                                        [stop["lat"], stop["lon"]],
                                        popup=f"{stop['name']}<br>Vehicle: {route['vehicle_id']}",
                                        tooltip=stop["name"],
                                        icon=folium.Icon(color=icon_color, icon=icon_type)
                                    ).add_to(m)

                            st_folium(m, width=None, height=500)
                        else:
                            st.info("No route data to display")

                    except ImportError:
                        st.warning("Install `folium` and `streamlit-folium` for map visualization")
                        # Fallback: show route details as table
                        for route in routes:
                            st.write(f"**{route['vehicle_id']}**: {route['num_stops']} stops, "
                                     f"{route['total_distance_km']} km, {route['total_load_kg']} kg")

                    # Route details table
                    st.subheader("📋 Route Details")
                    route_table = []
                    for r in routes:
                        stop_names = " → ".join([s["name"] for s in r["stops"]])
                        route_table.append({
                            "Vehicle": r["vehicle_id"],
                            "Stops": r["num_stops"],
                            "Route": stop_names[:80] + "..." if len(stop_names) > 80 else stop_names,
                            "Distance (km)": r["total_distance_km"],
                            "Time (min)": r["total_time_minutes"],
                            "Load (kg)": r["total_load_kg"],
                            "CO₂ (kg)": r["carbon_emission_kg"],
                        })
                    st.dataframe(pd.DataFrame(route_table), width='stretch', hide_index=True)
                else:
                    st.warning("No routes generated. Try running the Waste Cascade first.")

            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        st.info("👆 Configure settings and click **Optimize Routes** to generate optimized delivery routes.")

        # Show store locations  
        st.subheader("📍 Store & Hub Locations")
        try:
            stores = get_stores_dataframe()
            type_colors = {"retailer": "#1976D2", "food_bank": "#388E3C",
                           "compost_facility": "#EF6C00", "warehouse": "#7B1FA2"}
            fig = px.scatter_mapbox(
                stores, lat="latitude", lon="longitude",
                color="store_type", hover_name="name",
                hover_data=["city", "capacity_kg"],
                color_discrete_map=type_colors,
                zoom=3, height=500,
                mapbox_style="carto-positron"
            )
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, width='stretch')
        except Exception:
            st.info("Map requires data to be seeded first.")


# ══════════════════════════════════════════════════════════════
#  PAGE: CARBON IMPACT
# ══════════════════════════════════════════════════════════════

def page_carbon():
    st.markdown("## 🌍 Carbon Impact Tracker")
    st.markdown("Every kilogram of food saved = measurable CO₂ reduction")

    try:
        carbon = get_carbon_summary()
    except Exception:
        st.error("Database not initialized. Please run the data seeder first.")
        return

    total_co2 = carbon.get("total_waste_co2_kg", 0)
    cascade_saved = carbon.get("cascade_savings_co2_kg", 0)
    target_savings = total_co2 * 0.30
    equivalencies = get_equivalencies(target_savings)

    # ── Impact Cards ──
    st.subheader("🎯 Carbon Savings Potential (30% waste reduction)")
    eq_cols = st.columns(5)
    items = [
        ("🌳", "Trees Planted", f"{equivalencies['trees_planted']:,.0f}"),
        ("🚗", "Car KM Avoided", f"{equivalencies['car_km_avoided']:,.0f}"),
        ("✈️", "Flights Saved", f"{equivalencies['flights_avoided']:.1f}"),
        ("🏠", "Home-Days Powered", f"{equivalencies['homes_powered_days']:,.0f}"),
        ("📱", "Phone Charges", f"{equivalencies['smartphones_charged']:,.0f}"),
    ]
    for col, (icon, label, value) in zip(eq_cols, items):
        with col:
            st.metric(f"{icon} {label}", value)

    st.markdown("---")

    # ── CO₂ by Category ──
    st.subheader("📊 CO₂ Impact by Food Category")
    breakdown = carbon.get("category_breakdown", {})
    if breakdown:
        cat_data = []
        for cat, vals in breakdown.items():
            cat_data.append({
                "Category": cat,
                "Waste (kg)": vals["waste_kg"],
                "CO₂ Impact (kg)": vals["co2_impact_kg"],
                "CO₂ Factor": CARBON_FACTORS.get(cat, 1.5),
            })
        cat_df = pd.DataFrame(cat_data).sort_values("CO₂ Impact (kg)", ascending=False)

        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(cat_df, x="Category", y="CO₂ Impact (kg)",
                         color="CO₂ Impact (kg)", color_continuous_scale="Reds",
                         text="CO₂ Impact (kg)")
            fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig.update_layout(height=400, margin=dict(l=20, r=20, t=30, b=20), showlegend=False)
            st.plotly_chart(fig, width='stretch')

        with c2:
            fig = px.treemap(cat_df, path=["Category"], values="CO₂ Impact (kg)",
                             color="CO₂ Factor", color_continuous_scale="RdYlGn_r",
                             hover_data=["Waste (kg)"])
            fig.update_layout(height=400, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, width='stretch')

    # ── CO₂ Savings Progress ──
    st.subheader("🏆 Savings Progress")
    progress = (cascade_saved / target_savings * 100) if target_savings > 0 else 0
    st.progress(min(progress / 100, 1.0))
    pg1, pg2, pg3 = st.columns(3)
    with pg1:
        st.metric("Current CO₂ from Waste", format_co2(total_co2))
    with pg2:
        st.metric("Saved via Cascade", format_co2(cascade_saved))
    with pg3:
        st.metric("Target (30%)", format_co2(target_savings))

    # ── Carbon emission per product type ──
    st.subheader("🔬 Carbon Emission Factors (kg CO₂ per kg of food)")
    factor_df = pd.DataFrame([
        {"Category": k, "CO₂/kg": v, "Type": "High" if v > 5 else "Medium" if v > 1 else "Low"}
        for k, v in sorted(CARBON_FACTORS.items(), key=lambda x: x[1], reverse=True)
    ])
    fig = px.bar(factor_df, x="Category", y="CO₂/kg", color="Type",
                 color_discrete_map={"High": "#d32f2f", "Medium": "#ff9800", "Low": "#4caf50"},
                 text="CO₂/kg")
    fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, width='stretch')


# ══════════════════════════════════════════════════════════════
#  PAGE: ANALYTICS
# ══════════════════════════════════════════════════════════════

def page_analytics():
    st.markdown("## 📈 Deep Analytics")

    tab1, tab2, tab3, tab4 = st.tabs(["📅 Time Analysis", "🏪 Store Analysis", "📦 Product Analysis", "🏆 Leaderboard"])

    with tab1:
        st.subheader("Weekly & Monthly Waste Patterns")
        with get_db() as conn:
            weekly = conn.execute(f"""
                SELECT day_of_week, AVG(qty_wasted) as avg_waste, AVG(qty_sold) as avg_sold
                FROM sales s WHERE 1=1 {date_filter_sql} GROUP BY day_of_week ORDER BY day_of_week
            """).fetchdf()
            monthly = conn.execute(f"""
                SELECT month, SUM(qty_wasted) as total_waste, SUM(qty_sold) as total_sold,
                       SUM(waste_cost) as waste_cost
                FROM sales s WHERE 1=1 {date_filter_sql} GROUP BY month ORDER BY month
            """).fetchdf()

        dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        weekly["day_name"] = weekly["day_of_week"].map(lambda x: dow_names[x] if x < 7 else "?")

        w1, w2 = st.columns(2)
        with w1:
            fig = px.bar(weekly, x="day_name", y="avg_waste", color="avg_waste",
                         color_continuous_scale="OrRd",
                         labels={"avg_waste": "Avg Waste/Sale", "day_name": "Day"}, text="avg_waste")
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig.update_layout(height=350, showlegend=False, title="Average Waste by Day of Week")
            st.plotly_chart(fig, width='stretch')

        with w2:
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            monthly["month_name"] = monthly["month"].map(lambda x: month_names[x-1] if 1 <= x <= 12 else "?")
            monthly["waste_rate"] = monthly["total_waste"] / (monthly["total_sold"] + monthly["total_waste"]) * 100

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=monthly["month_name"], y=monthly["total_waste"],
                                 name="Total Waste", marker_color="#ef5350"), secondary_y=False)
            fig.add_trace(go.Scatter(x=monthly["month_name"], y=monthly["waste_rate"],
                                      name="Waste Rate %", line=dict(color="#ff9800", width=3)),
                          secondary_y=True)
            fig.update_layout(height=350, title="Monthly Waste Trend")
            fig.update_yaxes(title_text="Waste (kg)", secondary_y=False)
            fig.update_yaxes(title_text="Waste Rate %", secondary_y=True)
            st.plotly_chart(fig, width='stretch')

    with tab2:
        st.subheader("Store-Level Waste Analysis")
        with get_db() as conn:
            store_detail = conn.execute(f"""
                SELECT st.name, st.city, st.capacity_kg,
                       SUM(s.qty_sold) as sold, SUM(s.qty_wasted) as wasted,
                       SUM(s.revenue) as revenue, SUM(s.waste_cost) as waste_cost,
                       ROUND(SUM(s.qty_wasted)*100.0/NULLIF(SUM(s.qty_ordered),0), 2) as waste_rate
                FROM sales s JOIN stores st ON s.store_id = st.store_id
                WHERE st.store_type = 'retailer' {date_filter_sql}
                GROUP BY st.store_id, st.name, st.city, st.capacity_kg
            """).fetchdf()

        fig = px.scatter(store_detail, x="sold", y="wasted", size="revenue",
                         color="waste_rate", color_continuous_scale="RdYlGn_r",
                         hover_name="name", hover_data=["city", "waste_rate"],
                         labels={"sold": "Total Sold (kg)", "wasted": "Total Wasted (kg)"})
        fig.update_layout(height=450, title="Store Performance: Sales vs Waste")
        st.plotly_chart(fig, width='stretch')

        st.dataframe(store_detail.sort_values("waste_rate"), width='stretch', hide_index=True)

    with tab3:
        st.subheader("Product Waste Analysis by Shelf Life")
        with get_db() as conn:
            prod_analysis = conn.execute(f"""
                SELECT p.name, p.category, p.shelf_life_days, p.is_perishable,
                       SUM(s.qty_wasted) as waste_kg, SUM(s.waste_cost) as waste_cost,
                       AVG(s.qty_wasted/NULLIF(s.qty_ordered,0))*100 as waste_rate
                FROM sales s JOIN products p ON s.product_id = p.product_id
                WHERE 1=1 {date_filter_sql}
                GROUP BY p.product_id, p.name, p.category, p.shelf_life_days, p.is_perishable
                HAVING waste_kg > 0
                ORDER BY waste_kg DESC
            """).fetchdf()

        fig = px.scatter(prod_analysis, x="shelf_life_days", y="waste_rate",
                         size="waste_kg", color="category",
                         hover_name="name",
                         labels={"shelf_life_days": "Shelf Life (days)",
                                 "waste_rate": "Waste Rate %"})
        fig.update_layout(height=450, title="Shelf Life vs Waste Rate (bubble size = total waste)")
        st.plotly_chart(fig, width='stretch')

    with tab4:
        st.subheader("🏆 Store Leaderboard — Waste Efficiency Ranking")
        with get_db() as conn:
            leaderboard = conn.execute(f"""
                SELECT st.name, st.city,
                       SUM(s.qty_sold) as sold, SUM(s.qty_wasted) as wasted,
                       SUM(s.revenue) as revenue,
                       ROUND(SUM(s.qty_wasted)*100.0/NULLIF(SUM(s.qty_ordered),0), 2) as waste_rate
                FROM sales s JOIN stores st ON s.store_id = st.store_id
                WHERE st.store_type = 'retailer' {date_filter_sql}
                GROUP BY st.store_id, st.name, st.city
                ORDER BY waste_rate ASC
            """).fetchdf()

        leaderboard["Rank"] = range(1, len(leaderboard) + 1)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        leaderboard["Medal"] = leaderboard["Rank"].map(lambda x: medals.get(x, f"#{x}"))

        fig = px.bar(leaderboard, x="name", y="waste_rate", color="waste_rate",
                     color_continuous_scale="RdYlGn_r", text="waste_rate")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(height=400, title="Store Waste Rate Ranking (Lower is Better)",
                          xaxis_title="", yaxis_title="Waste Rate %")
        st.plotly_chart(fig, width='stretch')

        display_lb = leaderboard[["Medal", "name", "city", "sold", "wasted", "revenue", "waste_rate"]].copy()
        display_lb.columns = ["Rank", "Store", "City", "Sold (kg)", "Wasted (kg)", "Revenue ($)", "Waste Rate %"]
        st.dataframe(display_lb, width='stretch', hide_index=True)


# ══════════════════════════════════════════════════════════════
#  ROUTING
# ══════════════════════════════════════════════════════════════

# Route to correct page
page_map = {
    "📊 Overview Dashboard": page_overview,
    "🔮 Demand Forecast": page_forecast,
    "♻️ Waste Cascade": page_cascade,
    "🗺️ Route Optimizer": page_routes,
    "🌍 Carbon Impact": page_carbon,
    "📈 Analytics": page_analytics,
}

page_fn = page_map.get(page, page_overview)
page_fn()

# ── Footer ──
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#999;font-size:0.85rem;">'
    '🌿 FoodFlow AI — Hackathon 2026 | Waste Less. Feed More. Save Earth.'
    '</div>',
    unsafe_allow_html=True
)
