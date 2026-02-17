"""
FoodFlow AI — Agentic Dashboard Page
AI-powered dashboard with Mistral for insights, reports,
recommendations, Metabase MCP, and Word Document MCP.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import set_page_db
set_page_db("agentic")

import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from mistralai import Mistral
from utils.knowledge_base import build_knowledge_base, build_knowledge_text
from database.db import query_df, query_scalar

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "y3XeTHNpis5rOvfu6DSNMjcBEijTmrfX")
MODEL = "mistral-small-latest"

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
    .metric-row { display: flex; gap: 12px; margin-bottom: 16px; }
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
    .mcp-card {
        background: #16213e; padding: 18px; border-radius: 12px;
        border: 1px solid #0f3460; margin-bottom: 14px;
    }
    .mcp-card h4 { color: #f4a261; margin: 0 0 8px 0; }
    .mcp-card p { color: #ced4da; margin: 0; }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown("""
<div class="agent-header">
    <h1>🧠 FoodFlow AI — Agentic Dashboard</h1>
    <p>AI-powered analysis engine • Generates insights, reports & recommendations on demand</p>
</div>
""", unsafe_allow_html=True)


# ── Helper: Mistral call ──
def ask_mistral(prompt: str, system: str = None, max_tokens: int = 4000) -> str:
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
            "📄 Word Report Generator",
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

    ov = kb.get("platform_overview", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Transactions", f"{ov.get('total_transactions', 0):,}")
    c2.metric("💰 Revenue", f"${ov.get('total_revenue', 0):,.0f}")
    c3.metric("🗑️ Waste", f"{ov.get('total_waste_kg', 0):,.0f} kg")
    c4.metric("♻️ Food Redirected", f"{casc.get('total_food_redirected_kg', 0):,.0f} kg")

    st.markdown("---")

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

    col1, col2 = st.columns(2)
    with col1:
        trends = kb.get("monthly_trends", [])
        if trends:
            df = pd.DataFrame(trends)
            fig = px.bar(df, x="month", y=["sold_kg", "wasted_kg"],
                        title="Monthly Sales vs Waste",
                        barmode="group",
                        color_discrete_sequence=["#52b788", "#e94560"])
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        cats = kb.get("category_breakdown", [])
        if cats:
            df = pd.DataFrame(cats)
            fig = px.pie(df, values="total_wasted_kg", names="category",
                        title="Waste Distribution by Category",
                        color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
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
                system="You are a senior data analyst specializing in food supply chain optimization."
            )
            st.markdown(analysis)

    st.markdown("---")
    if "Store" in analysis_topic:
        stores = kb.get("store_performance", [])
        if stores:
            df = pd.DataFrame(stores)
            fig = px.bar(df, x="store_name", y="total_wasted_kg",
                        color="avg_waste_rate", title="Store Waste Comparison",
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
                        barmode="group", color_discrete_sequence=["#52b788", "#e94560"])
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
            st.plotly_chart(fig, use_container_width=True)

    elif "Cascade" in analysis_topic:
        casc_data = kb.get("cascade_optimization", {})
        tiers = casc_data.get("tiers", [])
        if tiers:
            df = pd.DataFrame(tiers)
            fig = px.bar(df, x="tier_name", y="total_kg",
                        color="carbon_saved_kg", title="Waste Cascade Tiers — Food Redirected",
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
                        system="You are a data analyst explaining query results to a business user."
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
3. **Action Items** — numbered list with what to do, who is responsible, expected impact, priority level
4. **Quick Wins** — actions that can show results within 1 week
5. **KPIs to Track** — dashboard metrics to monitor progress
6. **Risk Mitigation** — potential obstacles and solutions
7. **Expected ROI** — projected savings / impact

Use markdown with tables, bold numbers, and clear structure.""",
                system="You are a sustainability operations consultant. Create actionable, data-driven plans with specific, measurable outcomes."
            )
            st.markdown(plan)

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
        st.metric("Food Redirected", f"{casc.get('total_food_redirected_kg', 0):,.0f} kg",
                  delta="+Target: 3,000 kg")

    twp = kb.get("top_wasted_products", [])
    if twp:
        df = pd.DataFrame(twp[:10])
        fig = px.bar(df, x="name", y="total_wasted_kg",
                    color="category", title="Top 10 Products by Waste — Priority Targets",
                    color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════
#  MODE 6: Metabase Analytics (MCP Integration)
# ════════════════════════════════════════════════════════
elif agent_mode == "📈 Metabase Analytics":
    st.markdown("## 📈 Metabase Live Analytics Dashboard")
    st.markdown("""
    The FoodFlow Metabase dashboard provides **interactive, real-time analytics** 
    powered by DuckDB. Includes MCP (Model Context Protocol) integration for programmatic access.
    """)

    METABASE_URL = "http://localhost:3000"
    METABASE_DASHBOARD_ID = 2

    # Helper for Metabase API calls
    def metabase_api_call(endpoint: str, method: str = "GET", data: dict = None) -> dict:
        """Make authenticated Metabase API call."""
        import urllib.request
        try:
            # Auth
            auth_data = json.dumps({
                "username": "adhithanraja6@gmail.com",
                "password": "idlypoDa@12"
            }).encode()
            auth_req = urllib.request.Request(
                f"{METABASE_URL}/api/session",
                data=auth_data,
                headers={"Content-Type": "application/json"},
            )
            auth_resp = urllib.request.urlopen(auth_req, timeout=10)
            session_id = json.loads(auth_resp.read())["id"]

            # API call
            if data:
                req_data = json.dumps(data).encode()
            else:
                req_data = None
            req = urllib.request.Request(
                f"{METABASE_URL}{endpoint}",
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "X-Metabase-Session": session_id,
                },
                method=method,
            )
            resp = urllib.request.urlopen(req, timeout=30)
            return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e)}

    # Link to dashboard
    st.markdown(f"""
    <div class="mcp-card">
        <h4>🔗 Open Metabase Dashboard</h4>
        <p>Full interactive dashboard with filters, drill-downs, and sharing capabilities.</p>
        <a href="{METABASE_URL}/dashboard/{METABASE_DASHBOARD_ID}" target="_blank" 
           style="display: inline-block; background: #52b788; color: white; padding: 10px 24px; 
                  border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 8px;">
            Open Dashboard ↗
        </a>
    </div>
    """, unsafe_allow_html=True)

    # Tabs for different Metabase features
    mb_tab1, mb_tab2, mb_tab3, mb_tab4 = st.tabs([
        "📋 Cards & Queries", "🔧 MCP Actions", "📊 Create Card", "🗄️ Schema"
    ])

    with mb_tab1:
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

                if st.button(f"▶️ Execute Card {card['id']}", key=f"exec_card_{card['id']}"):
                    with st.spinner(f"Executing card {card['id']}..."):
                        result = metabase_api_call(f"/api/card/{card['id']}/query")
                        if "error" not in result:
                            cols = [c["name"] for c in result.get("data", {}).get("cols", [])]
                            rows = result.get("data", {}).get("rows", [])
                            if cols and rows:
                                df = pd.DataFrame(rows, columns=cols)
                                st.dataframe(df, use_container_width=True)
                                st.success(f"✅ {len(df)} rows")
                        else:
                            st.error(f"Error: {result['error']}")

        # Custom SQL query
        st.markdown("---")
        st.markdown("### ⚡ Run Custom SQL via Metabase")
        mb_query = st.text_area(
            "Enter DuckDB SQL query:",
            value="SELECT p.category, COUNT(*) as records, ROUND(SUM(s.qty_wasted), 0) as total_waste_kg\nFROM sales s JOIN products p ON s.product_id = p.product_id\nGROUP BY p.category\nORDER BY total_waste_kg DESC",
            height=120,
        )

        if st.button("🚀 Execute on Metabase", use_container_width=True):
            with st.spinner("Running query on Metabase DuckDB..."):
                result = metabase_api_call("/api/dataset", method="POST", data={
                    "database": 2,
                    "type": "native",
                    "native": {"query": mb_query}
                })
                if "error" not in result:
                    cols = [c["name"] for c in result.get("data", {}).get("cols", [])]
                    rows = result.get("data", {}).get("rows", [])
                    if cols and rows:
                        df = pd.DataFrame(rows, columns=cols)
                        st.dataframe(df, use_container_width=True)
                        st.success(f"✅ {len(df)} rows returned from Metabase DuckDB")

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
                else:
                    st.error(f"Metabase query error: {result['error']}")

    with mb_tab2:
        st.markdown("### 🔧 Metabase MCP Actions")
        st.markdown("""
        Perform administrative actions on the Metabase instance via MCP (Model Context Protocol).
        These actions allow programmatic management of dashboards, cards, and databases.
        """)

        mcp_action = st.selectbox("Select MCP Action", [
            "List All Dashboards",
            "List All Cards/Questions",
            "List All Databases",
            "Get Dashboard Details",
            "Sync Database Schema",
        ])

        if st.button("🔧 Execute MCP Action", use_container_width=True):
            with st.spinner(f"Executing: {mcp_action}..."):
                if mcp_action == "List All Dashboards":
                    result = metabase_api_call("/api/dashboard")
                    if isinstance(result, list):
                        for d in result:
                            st.markdown(f"- **Dashboard #{d.get('id')}**: {d.get('name', 'Untitled')} — {d.get('description', 'No description')}")
                    elif "error" in result:
                        st.error(result["error"])

                elif mcp_action == "List All Cards/Questions":
                    result = metabase_api_call("/api/card")
                    if isinstance(result, list):
                        card_df = pd.DataFrame([
                            {"ID": c["id"], "Name": c.get("name", ""), "Display": c.get("display", ""), "Collection": c.get("collection", {}).get("name", "Root") if c.get("collection") else "Root"}
                            for c in result
                        ])
                        st.dataframe(card_df, use_container_width=True)
                    elif "error" in result:
                        st.error(result["error"])

                elif mcp_action == "List All Databases":
                    result = metabase_api_call("/api/database")
                    if isinstance(result, dict) and "data" in result:
                        for db in result["data"]:
                            st.markdown(f"- **DB #{db['id']}**: {db['name']} ({db['engine']})")
                    elif "error" in result:
                        st.error(result["error"])

                elif mcp_action == "Get Dashboard Details":
                    result = metabase_api_call(f"/api/dashboard/{METABASE_DASHBOARD_ID}")
                    if "error" not in result:
                        st.json(result)
                    else:
                        st.error(result["error"])

                elif mcp_action == "Sync Database Schema":
                    result = metabase_api_call("/api/database/2/sync_schema", method="POST")
                    st.success("✅ Database schema sync triggered")

    with mb_tab3:
        st.markdown("### 📊 Create New Metabase Card")
        st.markdown("Generate a new Metabase question/card with AI-assisted SQL.")

        card_name = st.text_input("Card Name", value="Custom Analysis Card")
        card_desc = st.text_input("Description", value="AI-generated analysis card")
        card_display = st.selectbox("Display Type", ["table", "bar", "pie", "line", "scalar", "row"])

        ai_query_prompt = st.text_input(
            "Describe what data you want (AI will write SQL):",
            placeholder="e.g., Monthly waste cost trend by category"
        )

        if ai_query_prompt and st.button("🤖 Generate & Create Card", use_container_width=True):
            with st.spinner("AI writing SQL and creating card..."):
                sql = ask_mistral(
                    prompt=f"""Write a DuckDB SQL query for: "{ai_query_prompt}"
Tables: sales (date, store_id, product_id, qty_ordered, qty_sold, qty_wasted, revenue, waste_cost, day_of_week, month),
products (product_id, name, category, unit_cost, unit_price, carbon_footprint_kg),
stores (store_id, name, city, store_type), suppliers (name, city, reliability_score).
Return ONLY the SQL, no explanation.""",
                    system="SQL expert. Return only the query."
                )
                sql = sql.strip().strip("`").replace("```sql", "").replace("```", "").strip()
                st.code(sql, language="sql")

                card_data = {
                    "name": card_name,
                    "description": card_desc,
                    "display": card_display,
                    "dataset_query": {
                        "database": 2,
                        "type": "native",
                        "native": {"query": sql}
                    },
                    "visualization_settings": {}
                }
                result = metabase_api_call("/api/card", method="POST", data=card_data)
                if "error" not in result and "id" in result:
                    st.success(f"✅ Card created! ID: {result['id']}")
                    st.markdown(f"[Open Card ↗]({METABASE_URL}/question/{result['id']})")

                    if st.button("📌 Add to Dashboard", key="add_to_dash"):
                        dash_result = metabase_api_call(
                            f"/api/dashboard/{METABASE_DASHBOARD_ID}/cards",
                            method="PUT",
                            data={"cards": [{"id": result["id"], "card_id": result["id"],
                                            "row": 0, "col": 0, "size_x": 6, "size_y": 4}]}
                        )
                        st.success("✅ Card added to dashboard!")
                else:
                    st.error(f"Error creating card: {result.get('error', 'Unknown error')}")

    with mb_tab4:
        st.markdown("### 🗄️ Database Schema")
        if st.button("📖 Load Schema", use_container_width=True):
            with st.spinner("Loading schema..."):
                result = metabase_api_call("/api/database/2/metadata")
                if "error" not in result:
                    tables = result.get("tables", [])
                    for table in tables:
                        tname = table.get("name", "unknown")
                        fields = table.get("fields", [])
                        with st.expander(f"📋 {tname} ({len(fields)} columns)"):
                            for f in fields:
                                st.markdown(f"- `{f.get('name')}` — {f.get('database_type', 'unknown')} ({f.get('semantic_type', '')})")
                else:
                    st.error(result["error"])


# ════════════════════════════════════════════════════════
#  MODE 7: Word Report Generator (MCP Integration)
# ════════════════════════════════════════════════════════
elif agent_mode == "📄 Word Report Generator":
    st.markdown("## 📄 Word Document Report Generator")
    st.markdown("""
    Generate professional Word (.docx) reports using AI analysis and the Word Document MCP server.
    Reports include formatted tables, charts data, and executive insights.
    """)

    report_template = st.selectbox(
        "Report Template",
        [
            "Full Sustainability Report",
            "Executive Summary (1-page)",
            "Monthly Waste Analysis",
            "Carbon Impact Report",
            "Store Performance Report",
            "Board Presentation Briefing",
        ]
    )

    report_filename = st.text_input(
        "Report Filename",
        value=f"FoodFlow_{report_template.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.docx"
    )

    if st.button("📝 Generate Word Report", type="primary", use_container_width=True):
        with st.spinner(f"Generating {report_template}..."):
            # Generate content via AI
            report_content = ask_mistral(
                prompt=f"""Create content for a "{report_template}" about food waste reduction.

Platform Data:
{kb_text}

Generate the report with these sections (return as JSON):
{{
    "title": "Report title",
    "subtitle": "Subtitle",
    "sections": [
        {{
            "heading": "Section heading",
            "content": "Paragraph content with specific data",
            "table": null or {{"headers": ["col1", "col2"], "rows": [["val1", "val2"]]}}
        }}
    ],
    "key_metrics": {{"label": "value"}}
}}

Include at least 6 sections with real data from the platform.
Include 2-3 tables with actual data.
Be comprehensive and data-driven.""",
                system="Return ONLY valid JSON, no markdown fences.",
                max_tokens=5000,
            )

            try:
                # Parse JSON
                report_json = json.loads(report_content.strip().strip("`").replace("```json", "").replace("```", "").strip())

                # Build markdown preview
                st.markdown("### 📋 Report Preview")
                st.markdown(f"# {report_json.get('title', report_template)}")
                st.markdown(f"*{report_json.get('subtitle', '')}*")

                for section in report_json.get("sections", []):
                    st.markdown(f"## {section.get('heading', '')}")
                    st.markdown(section.get("content", ""))
                    if section.get("table"):
                        table = section["table"]
                        df = pd.DataFrame(table["rows"], columns=table["headers"])
                        st.dataframe(df, use_container_width=True, hide_index=True)

                # Generate downloadable markdown
                md_content = f"# {report_json.get('title', report_template)}\n\n"
                md_content += f"*{report_json.get('subtitle', '')}*\n\n"
                md_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"
                for section in report_json.get("sections", []):
                    md_content += f"## {section.get('heading', '')}\n\n"
                    md_content += f"{section.get('content', '')}\n\n"
                    if section.get("table"):
                        table = section["table"]
                        md_content += "| " + " | ".join(table["headers"]) + " |\n"
                        md_content += "| " + " | ".join(["---"] * len(table["headers"])) + " |\n"
                        for row in table["rows"]:
                            md_content += "| " + " | ".join(str(v) for v in row) + " |\n"
                        md_content += "\n"

                st.download_button(
                    "📥 Download Report (Markdown)",
                    data=md_content,
                    file_name=report_filename.replace(".docx", ".md"),
                    mime="text/markdown",
                    use_container_width=True,
                )

                st.success(f"✅ Report generated successfully!")
                st.info("💡 Tip: The existing Word report is available at `reports/FoodFlow_AI_Sustainability_Report_2025.docx`")

            except json.JSONDecodeError:
                st.markdown("### Generated Report")
                st.markdown(report_content)
                st.download_button(
                    "📥 Download Report (Markdown)",
                    data=report_content,
                    file_name=report_filename.replace(".docx", ".md"),
                    mime="text/markdown",
                    use_container_width=True,
                )

    # Show existing report
    st.markdown("---")
    st.markdown("### 📂 Existing Reports")
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    if os.path.exists(reports_dir):
        for f in os.listdir(reports_dir):
            if f.endswith(".docx"):
                fpath = os.path.join(reports_dir, f)
                fsize = os.path.getsize(fpath) / 1024
                st.markdown(f"""
                <div class="mcp-card">
                    <h4>📄 {f}</h4>
                    <p>Size: {fsize:.1f} KB | Generated via Word MCP Server</p>
                </div>
                """, unsafe_allow_html=True)
                with open(fpath, "rb") as fp:
                    st.download_button(
                        f"📥 Download {f}",
                        data=fp.read(),
                        file_name=f,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_{f}",
                        use_container_width=True,
                    )
    else:
        st.info("No reports found. Generate one above!")
