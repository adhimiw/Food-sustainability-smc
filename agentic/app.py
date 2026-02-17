"""
FoodFlow AI — Agentic Dashboard
AI-powered dashboard that uses Mistral to generate insights,
run analyses, and produce client-ready reports on demand.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from mistralai import Mistral
from utils.knowledge_base import build_knowledge_base, build_knowledge_text
from database.db import query_df, query_scalar, get_db

# ── Page Config ──
st.set_page_config(
    page_title="FoodFlow AI — Agentic Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
MODEL = os.environ.get("MISTRAL_MODEL", "mistral-large-2512").strip()
METABASE_URL = os.environ.get("METABASE_URL", "http://localhost:3000").strip()
METABASE_DASHBOARD_ID = int(os.environ.get("METABASE_DASHBOARD_ID", "2"))
METABASE_USERNAME = os.environ.get("METABASE_USERNAME", "").strip()
METABASE_PASSWORD = os.environ.get("METABASE_PASSWORD", "").strip()

# ── Dark theme CSS ──
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .agent-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 24px; border-radius: 14px; margin-bottom: 24px;
        text-align: center; color: white;
        border: 1px solid #e94560;
    }
    .agent-header h1 { color: white; margin: 0; font-size: 2rem; }
    .agent-header p { color: #a8dadc; margin: 8px 0 0 0; font-size: 1rem; }
    .insight-card {
        background: #1a1a2e; padding: 18px; border-radius: 12px;
        border-left: 4px solid #52b788; margin-bottom: 14px;
    }
    .insight-card h4 { color: #52b788; margin: 0 0 8px 0; }
    .insight-card p { color: #ced4da; margin: 0; line-height: 1.6; }
    .metric-row {
        display: flex; gap: 12px; margin-bottom: 16px;
    }
    .metric-box {
        background: #16213e; padding: 16px; border-radius: 10px;
        flex: 1; text-align: center; border: 1px solid #0f3460;
    }
    .metric-box .value { font-size: 1.6rem; font-weight: bold; color: #e94560; }
    .metric-box .label { color: #adb5bd; font-size: 0.8rem; }
    .report-section {
        background: #1a1a2e; padding: 20px; border-radius: 12px;
        border: 1px solid #2d2d44; margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown("""
<div class="agent-header">
    <h1>🧠 FoodFlow AI — Agentic Dashboard</h1>
    <p>AI-powered analysis engine • Generates insights, reports & recommendations on demand</p>
</div>
""", unsafe_allow_html=True)

if not MISTRAL_API_KEY:
    st.error("Missing MISTRAL_API_KEY. Set it in your environment before using Agentic Dashboard.")
    st.info("Example: export MISTRAL_API_KEY=your_key_here")
    st.stop()


# ── Helper: Mistral call ──
def ask_mistral(prompt: str, system: str = None, max_tokens: int = 4000) -> str:
    """Simple Mistral call for generating insights."""
    client = Mistral(api_key=MISTRAL_API_KEY)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.complete(model=MODEL, messages=messages, max_tokens=max_tokens)
    return response.choices[0].message.content


# ── Load knowledge base ──
@st.cache_data(ttl=300)
def load_kb():
    return build_knowledge_base()

@st.cache_data(ttl=300)
def load_kb_text():
    return build_knowledge_text()

kb = load_kb()
kb_text = load_kb_text()

# ── Sidebar ──
with st.sidebar:
    st.markdown("### 🧠 Agent Actions")
    agent_mode = st.radio(
        "Choose Analysis Mode",
        [
            "📊 Executive Summary",
            "🔍 Deep-Dive Analysis",
            "📋 Client Report Generator",
            "⚡ Live SQL Agent",
            "🎯 Action Recommendations",
            "📈 Metabase Analytics",
        ],
        index=0,
    )
    st.markdown("---")
    ov = kb.get("platform_overview", {})
    st.metric("Total Revenue", f"${ov.get('total_revenue', 0):,.0f}")
    st.metric("Waste Rate", f"{ov.get('waste_rate_pct', 0):.1f}%")
    st.metric("Waste Cost", f"${ov.get('total_waste_cost', 0):,.0f}")
    casc = kb.get("cascade_optimization", {})
    st.metric("CO₂ Saved", f"{casc.get('total_carbon_saved_kg', 0):,.0f} kg")


# ════════════════════════════════════════════════════════
#  MODE 1: Executive Summary
# ════════════════════════════════════════════════════════
if agent_mode == "📊 Executive Summary":
    st.markdown("## 📊 AI-Generated Executive Summary")

    # KPI row
    ov = kb.get("platform_overview", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Transactions", f"{ov.get('total_transactions', 0):,}")
    c2.metric("💰 Revenue", f"${ov.get('total_revenue', 0):,.0f}")
    c3.metric("🗑️ Waste", f"{ov.get('total_waste_kg', 0):,.0f} kg")
    c4.metric("♻️ Food Redirected", f"{casc.get('total_food_redirected_kg', 0):,.0f} kg")

    st.markdown("---")

    # AI-generated summary
    if st.button("🧠 Generate AI Executive Summary", use_container_width=True):
        with st.spinner("Mistral is analyzing your data..."):
            summary = ask_mistral(
                prompt=f"""Based on this food waste platform data, write a concise executive summary 
for the CEO/board. Cover: overall performance, waste reduction progress, AI forecasting impact,
carbon savings, and 3 key recommendations. Use specific numbers.

DATA:
{kb_text}""",
                system="You are a senior sustainability analyst writing an executive summary. Be concise, data-driven, and use markdown formatting with headers, bullets, and bold numbers."
            )
            st.markdown(summary)

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        trends = kb.get("monthly_trends", [])
        if trends:
            df = pd.DataFrame(trends)
            fig = px.bar(df, x="month", y=["sold_kg", "wasted_kg"],
                        title="Monthly Sales vs Waste",
                        barmode="group",
                        color_discrete_sequence=["#52b788", "#e94560"])
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0e1117",
                plot_bgcolor="#0e1117",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        cats = kb.get("category_breakdown", [])
        if cats:
            df = pd.DataFrame(cats)
            fig = px.pie(df, values="total_wasted_kg", names="category",
                        title="Waste Distribution by Category",
                        color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0e1117",
                plot_bgcolor="#0e1117",
            )
            st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════
#  MODE 2: Deep-Dive Analysis
# ════════════════════════════════════════════════════════
elif agent_mode == "🔍 Deep-Dive Analysis":
    st.markdown("## 🔍 AI Deep-Dive Analysis")

    analysis_topic = st.selectbox(
        "Select Analysis Topic",
        [
            "Category-Level Waste Analysis",
            "Store Performance Comparison",
            "Seasonal & Weather Patterns",
            "Waste Cascade Effectiveness",
            "Carbon Impact Assessment",
            "Inventory Risk Analysis",
            "Demand Forecasting Accuracy",
            "Supply Chain Efficiency",
        ]
    )

    if st.button("🔬 Run Deep Analysis", use_container_width=True):
        with st.spinner(f"Analyzing: {analysis_topic}..."):
            analysis = ask_mistral(
                prompt=f"""Perform a detailed deep-dive analysis on: "{analysis_topic}"

Use this data:
{kb_text}

Provide:
1. Key findings with specific data points
2. Trend analysis
3. Root cause identification
4. Comparison benchmarks
5. Actionable recommendations with expected impact
6. Risk factors to monitor

Format with clear markdown sections.""",
                system="You are a senior data analyst specializing in food supply chain optimization. Provide detailed, actionable analysis with specific numbers and clear recommendations."
            )
            st.markdown(analysis)

    # Quick stats for the selected topic
    st.markdown("---")
    if "Store" in analysis_topic:
        stores = kb.get("store_performance", [])
        if stores:
            df = pd.DataFrame(stores)
            fig = px.bar(df, x="store_name", y="total_wasted_kg",
                        color="avg_waste_rate",
                        title="Store Waste Comparison",
                        color_continuous_scale="RdYlGn_r")
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
            st.plotly_chart(fig, use_container_width=True)

    elif "Carbon" in analysis_topic:
        carbon = kb.get("carbon_impact", {})
        carb_cats = carbon.get("carbon_from_waste_by_category", [])
        if carb_cats:
            df = pd.DataFrame(carb_cats)
            fig = px.bar(df, x="category", y="carbon_from_waste_kg",
                        title="Carbon Emissions from Waste by Category",
                        color_discrete_sequence=["#e94560"])
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
            st.plotly_chart(fig, use_container_width=True)

    elif "Seasonal" in analysis_topic or "Weather" in analysis_topic:
        seas = kb.get("seasonality", [])
        if seas:
            df = pd.DataFrame(seas)
            fig = px.bar(df, x="day_name", y=["avg_sold", "avg_wasted"],
                        title="Day-of-Week Sales & Waste Pattern",
                        barmode="group",
                        color_discrete_sequence=["#52b788", "#e94560"])
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
            st.plotly_chart(fig, use_container_width=True)

    elif "Cascade" in analysis_topic:
        casc = kb.get("cascade_optimization", {})
        tiers = casc.get("tiers", [])
        if tiers:
            df = pd.DataFrame(tiers)
            fig = px.bar(df, x="tier_name", y="total_kg",
                        color="carbon_saved_kg",
                        title="Waste Cascade Tiers — Food Redirected",
                        color_continuous_scale="Greens")
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
            st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════
#  MODE 3: Client Report Generator
# ════════════════════════════════════════════════════════
elif agent_mode == "📋 Client Report Generator":
    st.markdown("## 📋 AI Client Report Generator")

    report_type = st.selectbox(
        "Report Type",
        [
            "Monthly Sustainability Report",
            "Waste Reduction Progress Report",
            "ROI & Financial Impact Report",
            "Carbon Footprint Report",
            "Operational Efficiency Report",
            "Board Presentation Summary",
        ]
    )

    audience = st.selectbox(
        "Target Audience",
        ["C-Suite / Board", "Operations Manager", "Sustainability Officer",
         "Store Manager", "External Stakeholder / Investor"]
    )

    include_recommendations = st.checkbox("Include AI Recommendations", value=True)
    include_forecast = st.checkbox("Include Future Projections", value=True)

    if st.button("📝 Generate Report", use_container_width=True):
        with st.spinner(f"Generating {report_type}..."):
            extras = ""
            if include_recommendations:
                extras += "\n- Include 5 specific, actionable recommendations with expected ROI"
            if include_forecast:
                extras += "\n- Include 3-month and 6-month projections based on current trends"

            report = ask_mistral(
                prompt=f"""Generate a professional "{report_type}" for the audience: "{audience}".

Platform Data:
{kb_text}

Requirements:
- Use formal business language appropriate for {audience}
- Include an executive summary at the top
- Use specific data points and metrics throughout
- Include comparison with industry benchmarks where possible
- Add a "Key Takeaways" section
- Format with clear markdown: headers, tables, bullets, bold key numbers
{extras}

Make it comprehensive, data-rich, and client-ready.""",
                system=f"You are a professional report writer for a food waste reduction AI platform. Write reports that are data-driven, visually organized with markdown, and tailored for {audience}.",
                max_tokens=6000,
            )

            st.markdown('<div class="report-section">', unsafe_allow_html=True)
            st.markdown(report)
            st.markdown('</div>', unsafe_allow_html=True)

            # Download button
            st.download_button(
                label="📥 Download Report (Markdown)",
                data=report,
                file_name=f"foodflow_{report_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                use_container_width=True,
            )


# ════════════════════════════════════════════════════════
#  MODE 4: Live SQL Agent
# ════════════════════════════════════════════════════════
elif agent_mode == "⚡ Live SQL Agent":
    st.markdown("## ⚡ AI-Powered SQL Agent")
    st.markdown("Ask questions in natural language — the AI writes and executes SQL queries on your live data.")

    question = st.text_input(
        "Ask a data question:",
        placeholder="e.g., What are the top 5 products by waste cost in December?"
    )

    if question and st.button("🚀 Run Query", use_container_width=True):
        with st.spinner("AI is writing SQL..."):
            # Step 1: Generate SQL
            sql_response = ask_mistral(
                prompt=f"""Convert this natural language question to a DuckDB SQL query:
                
Question: "{question}"

Available tables and columns:
- sales: sale_id, date, store_id, product_id, qty_ordered, qty_sold, qty_wasted, revenue, waste_cost, weather_temp, event_flag, day_of_week, month
- products: product_id, name, category, subcategory, shelf_life_days, avg_daily_demand, unit_cost, unit_price, carbon_footprint_kg, is_perishable
- stores: store_id, name, store_type, latitude, longitude, capacity_kg, city, address
- inventory: id, date, store_id, product_id, quantity_on_hand, days_until_expiry, freshness_score
- forecasts: forecast_id, created_at, store_id, product_id, forecast_date, predicted_demand, lower_bound, upper_bound, model_used, confidence
- waste_cascade_actions: action_id, created_at, source_store_id, destination_store_id, product_id, quantity_kg, cascade_tier, carbon_saved_kg, cost_saved, status
- weather: id, date, city, temp_c, humidity, precipitation_mm, wind_speed_kmh, condition
- events: event_id, date, event_name, event_type, city, impact_multiplier, affected_categories
- routes: route_id, created_at, vehicle_id, total_distance_km, total_time_minutes, total_load_kg, stops_json, carbon_emission_kg, status
- suppliers: supplier_id, name, latitude, longitude, lead_time_hours, reliability_score, capacity_kg_per_day, city

Return ONLY the SQL query, no explanation. Use DuckDB syntax. Limit results to 50 rows.""",
                system="You are a SQL expert. Return only the SQL query, nothing else. No markdown code fences."
            )

            # Clean the SQL (remove markdown fences if any)
            sql = sql_response.strip()
            if sql.startswith("```"):
                sql = "\n".join(sql.split("\n")[1:])
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip()

            st.code(sql, language="sql")

        with st.spinner("Executing query..."):
            try:
                df = query_df(sql)
                st.dataframe(df, use_container_width=True)
                st.success(f"✅ {len(df)} rows returned")

                # AI interpretation
                with st.spinner("AI interpreting results..."):
                    interpretation = ask_mistral(
                        prompt=f"""Interpret these SQL query results for a business user.

Question: "{question}"
SQL: {sql}
Results (first 20 rows):
{df.head(20).to_string()}

Provide:
1. A clear answer to the question
2. Key insights from the data
3. Any notable patterns or anomalies
4. A brief recommendation""",
                        system="You are a data analyst explaining query results to a business user. Be concise and insightful."
                    )
                    st.markdown("### 🧠 AI Interpretation")
                    st.markdown(interpretation)

            except Exception as e:
                st.error(f"Query Error: {str(e)}")


# ════════════════════════════════════════════════════════
#  MODE 5: Action Recommendations
# ════════════════════════════════════════════════════════
elif agent_mode == "🎯 Action Recommendations":
    st.markdown("## 🎯 AI Action Recommendations")

    priority_area = st.selectbox(
        "Priority Area",
        [
            "Reduce Overall Waste by 20%",
            "Maximize Carbon Savings",
            "Improve Store Efficiency",
            "Optimize Inventory Management",
            "Enhance Demand Forecasting",
            "Scale Cascade Operations",
            "Reduce Operational Costs",
        ]
    )

    time_horizon = st.selectbox(
        "Implementation Timeline",
        ["Immediate (this week)", "Short-term (1-3 months)",
         "Medium-term (3-6 months)", "Long-term (6-12 months)"]
    )

    if st.button("🎯 Generate Action Plan", use_container_width=True):
        with st.spinner(f"Creating action plan for: {priority_area}..."):
            plan = ask_mistral(
                prompt=f"""Create a detailed, actionable plan to achieve: "{priority_area}"
Timeline: {time_horizon}

Current Platform Data:
{kb_text}

Create a structured action plan with:
1. **Current State Assessment** — where we stand (use specific data)
2. **Target Metrics** — specific, measurable goals
3. **Action Items** — numbered list with:
   - What to do
   - Who is responsible (role)
   - Expected impact (quantified)
   - Priority level (Critical/High/Medium)
4. **Quick Wins** — actions that can show results within 1 week
5. **KPIs to Track** — dashboard metrics to monitor progress
6. **Risk Mitigation** — potential obstacles and solutions
7. **Expected ROI** — projected savings / impact

Use markdown with tables, bold numbers, and clear structure.""",
                system="You are a sustainability operations consultant. Create actionable, data-driven plans with specific, measurable outcomes. Every recommendation must be backed by data from the platform."
            )
            st.markdown(plan)

    # Show current performance gaps
    st.markdown("---")
    st.markdown("### 📊 Current Performance Snapshot")
    ov = kb.get("platform_overview", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Daily Waste", f"{ov.get('avg_daily_waste_kg', 0):,.0f} kg",
                  delta="-Target: <2,000 kg")
    with col2:
        st.metric("Waste Rate", f"{ov.get('waste_rate_pct', 0):.1f}%",
                  delta="-Target: <8%")
    with col3:
        casc = kb.get("cascade_optimization", {})
        st.metric("Food Redirected", f"{casc.get('total_food_redirected_kg', 0):,.0f} kg",
                  delta="+Target: 3,000 kg")

    # Top waste offenders chart
    twp = kb.get("top_wasted_products", [])
    if twp:
        df = pd.DataFrame(twp[:10])
        fig = px.bar(df, x="name", y="total_wasted_kg",
                    color="category",
                    title="Top 10 Products by Waste — Priority Targets",
                    color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            xaxis_tickangle=-45,
        )
        st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════
#  MODE 6: Metabase Analytics
# ════════════════════════════════════════════════════════
elif agent_mode == "📈 Metabase Analytics":
    st.markdown("## 📈 Metabase Live Analytics Dashboard")
    st.markdown("""
    The FoodFlow Metabase dashboard provides **interactive, real-time analytics** 
    powered by DuckDB. Click below to open it, or run custom queries directly.
    """)

    # Link to dashboard
    st.markdown(f"""
    <div style="background: #16213e; padding: 20px; border-radius: 12px; border: 1px solid #0f3460; margin-bottom: 20px;">
        <h3 style="color: #52b788; margin: 0;">🔗 Open Metabase Dashboard</h3>
        <p style="color: #ced4da; margin: 8px 0;">Full interactive dashboard with filters, drill-downs, and sharing capabilities.</p>
        <a href="{METABASE_URL}/dashboard/{METABASE_DASHBOARD_ID}" target="_blank" 
           style="display: inline-block; background: #52b788; color: white; padding: 10px 24px; 
                  border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 8px;">
            Open Dashboard ↗
        </a>
    </div>
    """, unsafe_allow_html=True)

    # Metabase cards listing
    st.markdown("---")
    st.markdown("### 📋 Available Analytics Cards")

    cards_info = [
        {"name": "Monthly Sales vs Waste Trend", "type": "Bar Chart", "id": 38,
         "desc": "Tracks monthly sold_kg vs wasted_kg across 2025"},
        {"name": "Waste by Category", "type": "Pie Chart", "id": 39,
         "desc": "Waste distribution across 13 product categories"},
        {"name": "Store Performance Table", "type": "Data Table", "id": 40,
         "desc": "Revenue, waste, and waste rate per store"},
        {"name": "Top 10 Wasted Products", "type": "Bar Chart", "id": 41,
         "desc": "Highest-waste products by quantity"},
        {"name": "Carbon Impact by Category", "type": "Bar Chart", "id": 42,
         "desc": "CO2 emissions from food waste per category"},
        {"name": "Day-of-Week Sales Pattern", "type": "Bar Chart", "id": 43,
         "desc": "Average sales and waste by day of week"},
    ]

    for card in cards_info:
        with st.expander(f"📊 {card['name']} ({card['type']})"):
            st.markdown(f"**Description:** {card['desc']}")
            st.markdown(f"**Card ID:** {card['id']}")
            st.markdown(f"[Open in Metabase ↗]({METABASE_URL}/question/{card['id']})")

    # Custom Metabase SQL query
    st.markdown("---")
    st.markdown("### ⚡ Run Custom SQL via Metabase")
    mb_query = st.text_area(
        "Enter DuckDB SQL query:",
        value="SELECT p.category, COUNT(*) as records, ROUND(SUM(s.qty_wasted), 0) as total_waste_kg\nFROM sales s JOIN products p ON s.product_id = p.product_id\nGROUP BY p.category\nORDER BY total_waste_kg DESC",
        height=120,
    )

    if st.button("🚀 Execute on Metabase", use_container_width=True):
        with st.spinner("Running query on Metabase DuckDB..."):
            try:
                import urllib.request

                # Authenticate with Metabase
                if not METABASE_USERNAME or not METABASE_PASSWORD:
                    raise RuntimeError("Missing METABASE_USERNAME / METABASE_PASSWORD environment variables")

                auth_data = json.dumps({
                    "username": METABASE_USERNAME,
                    "password": METABASE_PASSWORD
                }).encode()
                auth_req = urllib.request.Request(
                    f"{METABASE_URL}/api/session",
                    data=auth_data,
                    headers={"Content-Type": "application/json"},
                )
                auth_resp = urllib.request.urlopen(auth_req, timeout=10)
                session_id = json.loads(auth_resp.read())["id"]

                # Execute query
                query_data = json.dumps({
                    "database": 2,
                    "type": "native",
                    "native": {"query": mb_query}
                }).encode()
                query_req = urllib.request.Request(
                    f"{METABASE_URL}/api/dataset",
                    data=query_data,
                    headers={
                        "Content-Type": "application/json",
                        "X-Metabase-Session": session_id,
                    },
                )
                query_resp = urllib.request.urlopen(query_req, timeout=30)
                result = json.loads(query_resp.read())

                # Parse results into dataframe
                cols = [c["name"] for c in result["data"]["cols"]]
                rows = result["data"]["rows"]
                df = pd.DataFrame(rows, columns=cols)
                st.dataframe(df, use_container_width=True)
                st.success(f"✅ {len(df)} rows returned from Metabase DuckDB")

                # AI interpretation
                if len(df) > 0:
                    with st.spinner("AI interpreting results..."):
                        interpretation = ask_mistral(
                            prompt=f"""Interpret these Metabase query results:

SQL: {mb_query}
Results:
{df.head(20).to_string()}

Provide key insights and recommendations.""",
                            system="You are a data analyst. Be concise and insightful.",
                            max_tokens=1000,
                        )
                        st.markdown("### 🧠 AI Interpretation")
                        st.markdown(interpretation)

            except Exception as e:
                st.error(f"Metabase query error: {str(e)}")
