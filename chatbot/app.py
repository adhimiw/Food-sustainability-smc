"""
FoodFlow AI — Mistral-Powered Chatbot
Interactive Q&A with chart visualizations over the FoodFlow knowledge base.
Answers client questions about waste, demand, carbon impact, and more.
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
from utils.knowledge_base import (
    build_knowledge_text,
    build_knowledge_base,
    run_custom_query,
)
from database.db import query_df, query_scalar

# ── Page Config ──
st.set_page_config(
    page_title="FoodFlow AI Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ──
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "y3XeTHNpis5rOvfu6DSNMjcBEijTmrfX")
MODEL = "mistral-small-latest"

# ── 20 Pre-built Questions ──
PREBUILT_QUESTIONS = [
    # 0 - Overview & KPIs
    {"q": "What is our overall waste rate and total waste cost?", "icon": "📊",
     "sql": "SELECT COUNT(*) as transactions, ROUND(SUM(qty_sold),0) as sold_kg, ROUND(SUM(qty_wasted),0) as wasted_kg, ROUND(SUM(revenue),0) as revenue, ROUND(SUM(waste_cost),0) as waste_cost, ROUND(SUM(qty_wasted)/NULLIF(SUM(qty_ordered),0)*100,2) as waste_rate_pct FROM sales",
     "chart": "kpi"},

    # 1 - Monthly Trends
    {"q": "Show me monthly waste and sales trends", "icon": "📈",
     "sql": "SELECT SUBSTR(date,1,7) as month, ROUND(SUM(qty_sold),0) as sold_kg, ROUND(SUM(qty_wasted),0) as wasted_kg, ROUND(SUM(revenue),0) as revenue, ROUND(SUM(waste_cost),0) as waste_cost FROM sales GROUP BY SUBSTR(date,1,7) ORDER BY month",
     "chart": "bar", "x": "month", "y": ["sold_kg", "wasted_kg"], "title": "Monthly Sales vs Waste (kg)"},

    # 2 - Category Breakdown
    {"q": "Which food categories waste the most?", "icon": "🍕",
     "sql": "SELECT p.category, ROUND(SUM(s.qty_wasted),0) as wasted_kg, ROUND(SUM(s.waste_cost),0) as waste_cost, ROUND(AVG(s.qty_wasted/NULLIF(s.qty_ordered,0))*100,1) as waste_rate FROM sales s JOIN products p ON s.product_id=p.product_id GROUP BY p.category ORDER BY wasted_kg DESC",
     "chart": "pie", "values": "wasted_kg", "names": "category", "title": "Waste Distribution by Category"},

    # 3 - Store Performance
    {"q": "Compare waste rates across all stores", "icon": "🏪",
     "sql": "SELECT st.name, st.city, ROUND(SUM(s.revenue),0) as revenue, ROUND(SUM(s.qty_wasted),0) as waste_kg, ROUND(AVG(s.qty_wasted/NULLIF(s.qty_ordered,0))*100,1) as waste_rate FROM sales s JOIN stores st ON s.store_id=st.store_id GROUP BY st.name, st.city ORDER BY waste_rate DESC",
     "chart": "bar_h", "x": "waste_rate", "y": "name", "color": "waste_rate", "title": "Store Waste Rates (%)"},

    # 4 - Top Wasted Products
    {"q": "What are the top 10 most wasted products?", "icon": "🗑️",
     "sql": "SELECT p.name, p.category, ROUND(SUM(s.qty_wasted),0) as wasted_kg, ROUND(SUM(s.waste_cost),0) as waste_cost FROM sales s JOIN products p ON s.product_id=p.product_id GROUP BY p.name, p.category ORDER BY wasted_kg DESC LIMIT 10",
     "chart": "bar_h", "x": "wasted_kg", "y": "name", "color": "category", "title": "Top 10 Wasted Products (kg)"},

    # 5 - Carbon Impact
    {"q": "What is our carbon footprint from food waste?", "icon": "🌍",
     "sql": "SELECT p.category, ROUND(SUM(s.qty_wasted * p.carbon_footprint_kg),0) as carbon_kg, ROUND(SUM(s.qty_wasted),0) as waste_kg FROM sales s JOIN products p ON s.product_id=p.product_id GROUP BY p.category ORDER BY carbon_kg DESC",
     "chart": "bar", "x": "category", "y": ["carbon_kg"], "title": "Carbon Emissions from Waste by Category (kg CO₂)"},

    # 6 - Day-of-Week Pattern
    {"q": "Which days of the week have the most waste?", "icon": "📅",
     "sql": "SELECT CASE DAYOFWEEK(CAST(date AS DATE)) WHEN 1 THEN 'Sun' WHEN 2 THEN 'Mon' WHEN 3 THEN 'Tue' WHEN 4 THEN 'Wed' WHEN 5 THEN 'Thu' WHEN 6 THEN 'Fri' WHEN 7 THEN 'Sat' END as day, DAYOFWEEK(CAST(date AS DATE)) as d, ROUND(AVG(qty_sold),2) as avg_sold, ROUND(AVG(qty_wasted),2) as avg_wasted FROM sales GROUP BY DAYOFWEEK(CAST(date AS DATE)) ORDER BY d",
     "chart": "bar", "x": "day", "y": ["avg_sold", "avg_wasted"], "title": "Day-of-Week Avg Sales vs Waste"},

    # 7 - Cascade Optimization
    {"q": "How effective is our waste cascade redistribution?", "icon": "♻️",
     "sql": "SELECT cascade_tier, COUNT(*) as actions, ROUND(SUM(quantity_kg),0) as total_kg, ROUND(SUM(carbon_saved_kg),0) as carbon_saved, ROUND(SUM(cost_saved),0) as cost_saved FROM waste_cascade_actions WHERE status='completed' GROUP BY cascade_tier ORDER BY cascade_tier",
     "chart": "bar", "x": "cascade_tier", "y": ["total_kg", "carbon_saved"], "title": "Waste Cascade Performance by Tier"},

    # 8 - Revenue Analysis
    {"q": "What's our monthly revenue trend?", "icon": "💰",
     "sql": "SELECT SUBSTR(date,1,7) as month, ROUND(SUM(revenue),0) as revenue, ROUND(SUM(waste_cost),0) as waste_cost, ROUND(SUM(revenue)-SUM(waste_cost),0) as net_revenue FROM sales GROUP BY SUBSTR(date,1,7) ORDER BY month",
     "chart": "line", "x": "month", "y": ["revenue", "waste_cost"], "title": "Monthly Revenue vs Waste Cost ($)"},

    # 9 - Weather Impact
    {"q": "How does weather temperature affect waste?", "icon": "🌡️",
     "sql": "SELECT CASE WHEN weather_temp < 10 THEN 'Cold (<10°C)' WHEN weather_temp < 20 THEN 'Cool (10-20°C)' WHEN weather_temp < 30 THEN 'Warm (20-30°C)' ELSE 'Hot (30+°C)' END as temp_range, ROUND(AVG(qty_wasted),2) as avg_waste, ROUND(AVG(qty_sold),2) as avg_sold, COUNT(*) as records FROM sales GROUP BY CASE WHEN weather_temp < 10 THEN 'Cold (<10°C)' WHEN weather_temp < 20 THEN 'Cool (10-20°C)' WHEN weather_temp < 30 THEN 'Warm (20-30°C)' ELSE 'Hot (30+°C)' END ORDER BY avg_waste DESC",
     "chart": "bar", "x": "temp_range", "y": ["avg_waste", "avg_sold"], "title": "Weather Impact on Waste & Sales"},

    # 10 - Inventory Health
    {"q": "How many products are expiring soon?", "icon": "⏰",
     "sql": "SELECT CASE WHEN days_until_expiry <= 1 THEN 'Expired/Today' WHEN days_until_expiry <= 3 THEN '1-3 Days' WHEN days_until_expiry <= 7 THEN '4-7 Days' ELSE '7+ Days' END as urgency, COUNT(*) as items, ROUND(SUM(quantity_on_hand),0) as total_qty, ROUND(AVG(freshness_score),1) as avg_freshness FROM inventory GROUP BY CASE WHEN days_until_expiry <= 1 THEN 'Expired/Today' WHEN days_until_expiry <= 3 THEN '1-3 Days' WHEN days_until_expiry <= 7 THEN '4-7 Days' ELSE '7+ Days' END ORDER BY MIN(days_until_expiry)",
     "chart": "bar", "x": "urgency", "y": ["items"], "title": "Inventory Expiry Risk Distribution"},

    # 11 - Best vs Worst Stores
    {"q": "Which stores perform best and worst on waste?", "icon": "🏆",
     "sql": "SELECT st.name, st.city, ROUND(SUM(s.revenue),0) as revenue, ROUND(SUM(s.qty_wasted),0) as waste_kg, ROUND(AVG(s.qty_wasted/NULLIF(s.qty_ordered,0))*100,1) as waste_rate, ROUND(SUM(s.waste_cost),0) as waste_cost FROM sales s JOIN stores st ON s.store_id=st.store_id GROUP BY st.name, st.city ORDER BY waste_rate ASC",
     "chart": "table"},

    # 12 - Forecast Accuracy
    {"q": "How accurate is our AI demand forecasting?", "icon": "🎯",
     "sql": "SELECT model_used, COUNT(*) as forecasts, ROUND(AVG(confidence),3) as avg_confidence, ROUND(AVG(predicted_demand),1) as avg_predicted FROM forecasts GROUP BY model_used",
     "chart": "table"},

    # 13 - Perishable vs Non-Perishable
    {"q": "How do perishable products compare to non-perishable?", "icon": "🥬",
     "sql": "SELECT CASE WHEN p.is_perishable=true THEN 'Perishable' ELSE 'Non-Perishable' END as type, COUNT(DISTINCT p.product_id) as products, ROUND(SUM(s.qty_wasted),0) as waste_kg, ROUND(SUM(s.waste_cost),0) as waste_cost, ROUND(AVG(s.qty_wasted/NULLIF(s.qty_ordered,0))*100,1) as waste_rate FROM sales s JOIN products p ON s.product_id=p.product_id GROUP BY p.is_perishable",
     "chart": "bar", "x": "type", "y": ["waste_kg", "waste_cost"], "title": "Perishable vs Non-Perishable Waste"},

    # 14 - Supplier Reliability
    {"q": "Which suppliers are most and least reliable?", "icon": "🚚",
     "sql": "SELECT name, city, ROUND(reliability_score,2) as reliability, ROUND(capacity_kg_per_day,0) as capacity_kg, ROUND(lead_time_hours,0) as lead_hours FROM suppliers ORDER BY reliability_score DESC",
     "chart": "bar_h", "x": "reliability", "y": "name", "color": "reliability", "title": "Supplier Reliability Scores"},

    # 15 - Monthly Waste Rate Trend
    {"q": "Is our waste rate improving or getting worse over time?", "icon": "📉",
     "sql": "SELECT SUBSTR(date,1,7) as month, ROUND(SUM(qty_wasted)/NULLIF(SUM(qty_ordered),0)*100,2) as waste_rate, ROUND(SUM(qty_wasted),0) as waste_kg FROM sales GROUP BY SUBSTR(date,1,7) ORDER BY month",
     "chart": "line", "x": "month", "y": ["waste_rate"], "title": "Monthly Waste Rate Trend (%)"},

    # 16 - Route Optimization
    {"q": "How efficient are our delivery routes?", "icon": "🗺️",
     "sql": "SELECT vehicle_id, COUNT(*) as routes, ROUND(AVG(total_distance_km),1) as avg_distance, ROUND(AVG(total_time_minutes),0) as avg_time, ROUND(AVG(total_load_kg),0) as avg_load, ROUND(SUM(carbon_emission_kg),0) as total_carbon FROM routes GROUP BY vehicle_id ORDER BY total_carbon ASC",
     "chart": "bar", "x": "vehicle_id", "y": ["avg_distance", "total_carbon"], "title": "Route Efficiency by Vehicle"},

    # 17 - High-Value Waste
    {"q": "Which products cause the highest waste cost?", "icon": "💸",
     "sql": "SELECT p.name, p.category, ROUND(SUM(s.waste_cost),0) as waste_cost, ROUND(SUM(s.qty_wasted),0) as waste_kg, ROUND(AVG(p.unit_price),2) as avg_price FROM sales s JOIN products p ON s.product_id=p.product_id GROUP BY p.name, p.category ORDER BY waste_cost DESC LIMIT 10",
     "chart": "bar_h", "x": "waste_cost", "y": "name", "color": "category", "title": "Top 10 Products by Waste Cost ($)"},

    # 18 - City-Level Analysis
    {"q": "How does waste compare across cities?", "icon": "🌆",
     "sql": "SELECT st.city, COUNT(DISTINCT st.store_id) as stores, ROUND(SUM(s.revenue),0) as revenue, ROUND(SUM(s.qty_wasted),0) as waste_kg, ROUND(SUM(s.waste_cost),0) as waste_cost, ROUND(AVG(s.qty_wasted/NULLIF(s.qty_ordered,0))*100,1) as waste_rate FROM sales s JOIN stores st ON s.store_id=st.store_id GROUP BY st.city ORDER BY waste_kg DESC",
     "chart": "bar", "x": "city", "y": ["waste_kg", "revenue"], "title": "Waste & Revenue by City"},

    # 19 - Executive Summary
    {"q": "Give me a full executive summary for the board", "icon": "👔",
     "sql": None, "chart": "ai_only"},
]


SYSTEM_PROMPT = """You are FoodFlow AI Assistant — an expert AI analyst for a food waste reduction platform.
You have complete access to the platform's data and analytics.
Your role is to help clients (grocery store managers, sustainability officers, executives) understand:
- Food waste patterns, costs, and trends
- Demand forecasting accuracy and predictions
- Waste cascade optimization results (redistribution, food banks, composting)
- Carbon footprint impact and savings
- Store-level and product-level performance
- Inventory health and expiring items
- Route optimization for food redistribution
- Weather and seasonality effects on waste

GUIDELINES:
1. Always be data-driven — cite specific numbers from the knowledge base
2. When discussing waste, always mention both kg AND cost impact
3. Proactively suggest actionable insights and recommendations
4. Compare metrics across stores, categories, and time periods
5. Explain the waste cascade tiers when relevant (Tier 1: Redistribution, Tier 2: Food Banks, Tier 3: Composting)
6. Highlight carbon impact in terms people understand (e.g., "equivalent to X car trips")
7. Be professional but approachable — this is a B2B analytics assistant
8. If asked about data you don't have, say so clearly and suggest what data would help
9. Format numbers with commas and appropriate units (kg, $, %, CO2)
10. Use markdown formatting for clarity (bold, bullets, tables when appropriate)

KNOWLEDGE BASE (current platform data):
{knowledge_base}
"""


# ── Tool definitions for function calling ──
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Run a SQL query against the FoodFlow DuckDB database to get real-time data. Use this when the knowledge base doesn't have the specific data the user is asking about, or when they need very specific drill-down analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A valid DuckDB SQL query. Available tables: sales (date, store_id, product_id, qty_ordered, qty_sold, qty_wasted, revenue, waste_cost, weather_temp, event_flag, day_of_week, month), products (product_id, name, category, subcategory, shelf_life_days, avg_daily_demand, unit_cost, unit_price, carbon_footprint_kg, is_perishable), stores (store_id, name, store_type, latitude, longitude, capacity_kg, city, address), inventory (date, store_id, product_id, quantity_on_hand, days_until_expiry, freshness_score), forecasts (store_id, product_id, forecast_date, predicted_demand, model_used, confidence), waste_cascade_actions (source_store_id, destination_store_id, product_id, quantity_kg, cascade_tier, carbon_saved_kg, cost_saved, status), weather (date, city, temp_c, humidity, precipitation_mm, condition), events (date, event_name, event_type, city, impact_multiplier)"
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_themed_analysis",
            "description": "Get a pre-built themed analysis. Use when the user asks about a broad topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "theme": {
                        "type": "string",
                        "enum": ["worst_stores", "best_stores", "expiring_soon", "high_demand", "recent_cascades"],
                        "description": "The analytical theme to explore"
                    }
                },
                "required": ["theme"]
            }
        }
    }
]


def execute_tool_call(tool_name: str, args: dict) -> str:
    """Execute a tool call and return the result as a string."""
    if tool_name == "query_database":
        sql = args.get("sql", "")
        try:
            df = query_df(sql)
            if df.empty:
                return "Query returned no results."
            return df.to_string(index=False, max_rows=30)
        except Exception as e:
            return f"SQL Error: {str(e)}"
    elif tool_name == "get_themed_analysis":
        theme = args.get("theme", "")
        return run_custom_query(theme)
    return "Unknown tool."


def get_chat_response(messages: list, knowledge_text: str) -> str:
    """Get a response from Mistral with tool-calling support."""
    client = Mistral(api_key=MISTRAL_API_KEY)

    system_msg = SYSTEM_PROMPT.format(knowledge_base=knowledge_text)
    full_messages = [{"role": "system", "content": system_msg}] + messages

    response = client.chat.complete(
        model=MODEL,
        messages=full_messages,
        tools=TOOLS,
        tool_choice="auto",
    )

    msg = response.choices[0].message

    # Handle tool calls (up to 3 rounds)
    rounds = 0
    while msg.tool_calls and rounds < 3:
        rounds += 1
        full_messages.append(msg)

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)
            result = execute_tool_call(fn_name, fn_args)
            full_messages.append({
                "role": "tool",
                "name": fn_name,
                "content": result,
                "tool_call_id": tc.id,
            })

        response = client.chat.complete(
            model=MODEL,
            messages=full_messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

    return msg.content


def render_chart(df: pd.DataFrame, spec: dict):
    """Render a Plotly chart based on the question spec."""
    chart_type = spec.get("chart", "table")
    title = spec.get("title", "")

    dark_layout = dict(
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#ced4da"),
        title=dict(font=dict(color="white")),
    )

    if chart_type == "kpi":
        if not df.empty:
            row = df.iloc[0]
            labels = {
                "transactions": ("📦 Transactions", "{:,.0f}"),
                "sold_kg": ("📈 Sold", "{:,.0f} kg"),
                "wasted_kg": ("🗑️ Wasted", "{:,.0f} kg"),
                "revenue": ("💰 Revenue", "${:,.0f}"),
                "waste_cost": ("💸 Waste Cost", "${:,.0f}"),
                "waste_rate_pct": ("📊 Waste Rate", "{:.2f}%"),
            }
            cols = st.columns(len(df.columns))
            for col_st, col_name in zip(cols, df.columns):
                label, fmt = labels.get(col_name, (col_name, "{:,.2f}"))
                val = row[col_name]
                col_st.metric(label, fmt.format(val))

    elif chart_type == "bar":
        fig = px.bar(df, x=spec["x"], y=spec["y"], title=title,
                     barmode="group",
                     color_discrete_sequence=["#52b788", "#e94560", "#f4a261", "#457b9d"])
        fig.update_layout(**dark_layout, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "bar_h":
        fig = px.bar(df, x=spec["x"], y=spec["y"], title=title,
                     orientation="h",
                     color=spec.get("color"),
                     color_continuous_scale="RdYlGn" if spec.get("color") == "reliability" else "RdYlGn_r")
        fig.update_layout(**dark_layout)
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "pie":
        fig = px.pie(df, values=spec["values"], names=spec["names"], title=title,
                     color_discrete_sequence=px.colors.qualitative.Set3)
        fig.update_layout(**dark_layout)
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "line":
        fig = px.line(df, x=spec["x"], y=spec["y"], title=title,
                      markers=True,
                      color_discrete_sequence=["#52b788", "#e94560", "#f4a261"])
        fig.update_layout(**dark_layout)
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "table":
        st.dataframe(df, use_container_width=True)


# ════════════════════════════════════════════════════════
#  Streamlit UI
# ════════════════════════════════════════════════════════

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .chat-header {
        background: linear-gradient(135deg, #1a472a 0%, #2d6a4f 100%);
        padding: 20px; border-radius: 12px; margin-bottom: 20px;
        text-align: center; color: white;
    }
    .chat-header h1 { color: white; margin: 0; font-size: 1.8rem; }
    .chat-header p { color: #b7e4c7; margin: 5px 0 0 0; }
    .stChatMessage { border-radius: 12px; }
    .sidebar-info {
        background: #1a1a2e; padding: 15px; border-radius: 10px;
        border: 1px solid #2d2d44; margin-bottom: 15px;
    }
    .sidebar-info h4 { color: #52b788; margin: 0 0 8px 0; }
    .sidebar-info p { color: #adb5bd; font-size: 0.85rem; margin: 3px 0; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="chat-header">
    <h1>🤖 FoodFlow AI Chatbot</h1>
    <p>Ask anything about food waste, demand forecasting, carbon impact & more — with live visualizations</p>
</div>
""", unsafe_allow_html=True)

# ── Initialize session state ──
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "knowledge_text" not in st.session_state:
    with st.spinner("Loading knowledge base..."):
        st.session_state.knowledge_text = build_knowledge_text()
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── Sidebar ──
with st.sidebar:
    st.markdown("### 💬 Chat Controls")
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_messages = []
        st.session_state.pending_question = None
        st.rerun()

    st.markdown("---")
    st.markdown("### 📋 Quick Questions (20 pre-built)")

    categories = {
        "📊 Overview & KPIs": [0, 8, 15],
        "📈 Trends & Patterns": [1, 6, 9],
        "🍕 Categories & Products": [2, 4, 13, 17],
        "🏪 Stores & Cities": [3, 11, 18],
        "🌍 Sustainability": [5, 7, 16],
        "⚙️ Operations": [10, 12, 14],
        "👔 Executive": [19],
    }

    for cat_name, indices in categories.items():
        with st.expander(cat_name, expanded=False):
            for idx in indices:
                pq = PREBUILT_QUESTIONS[idx]
                if st.button(f"{pq['icon']} {pq['q']}", key=f"pq_{idx}", use_container_width=True):
                    st.session_state.pending_question = idx
                    st.rerun()

    st.markdown("---")
    st.markdown(f"**Model:** `{MODEL}`")
    st.markdown(f"**Knowledge Base:** Live DuckDB")
    st.markdown(f"**Charts:** Plotly Interactive")
    st.markdown(f"**Questions:** 20 pre-built + free-text")


# ── Display existing chat messages ──
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("chart_data") is not None and msg.get("chart_spec"):
            try:
                df = pd.DataFrame(msg["chart_data"])
                render_chart(df, msg["chart_spec"])
            except Exception:
                pass


# ── Handle pending prebuilt question ──
if st.session_state.pending_question is not None:
    idx = st.session_state.pending_question
    st.session_state.pending_question = None
    pq = PREBUILT_QUESTIONS[idx]
    question = pq["q"]

    st.session_state.chat_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if pq["chart"] == "ai_only":
            with st.spinner("Generating AI analysis..."):
                response = get_chat_response(
                    [{"role": "user", "content": question}],
                    st.session_state.knowledge_text,
                )
                st.markdown(response)
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": response}
                )
        else:
            with st.spinner("Querying database & generating visualization..."):
                try:
                    df = query_df(pq["sql"])

                    if df.empty:
                        st.warning("No data returned.")
                        st.session_state.chat_messages.append(
                            {"role": "assistant", "content": "No data returned for this query."}
                        )
                    else:
                        render_chart(df, pq)

                        ai_prompt = f"""The user asked: "{question}"
Here are the query results:
{df.head(20).to_string()}

Provide a clear, insightful interpretation of this data with:
1. Direct answer to the question with key numbers
2. Notable patterns or anomalies
3. 2-3 actionable recommendations
Be concise and use markdown formatting."""

                        interpretation = get_chat_response(
                            [{"role": "user", "content": ai_prompt}],
                            st.session_state.knowledge_text,
                        )
                        st.markdown("---")
                        st.markdown("### 🧠 AI Analysis")
                        st.markdown(interpretation)

                        st.session_state.chat_messages.append({
                            "role": "assistant",
                            "content": interpretation,
                            "chart_data": df.to_dict(orient="records"),
                            "chart_spec": {k: v for k, v in pq.items() if k not in ("q", "icon", "sql")},
                        })

                except Exception as e:
                    error_msg = f"Query Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": error_msg}
                    )

    st.rerun()


# ── Free-text Chat input ──
if prompt := st.chat_input("Ask me anything about FoodFlow AI..."):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Check if it matches a prebuilt question (fuzzy)
    matched_pq = None
    prompt_lower = prompt.lower().strip()
    for pq in PREBUILT_QUESTIONS:
        if pq["q"].lower() in prompt_lower or prompt_lower in pq["q"].lower():
            if pq.get("sql") and pq["chart"] != "ai_only":
                matched_pq = pq
                break

    with st.chat_message("assistant"):
        if matched_pq:
            with st.spinner("Querying & visualizing..."):
                try:
                    df = query_df(matched_pq["sql"])
                    if not df.empty:
                        render_chart(df, matched_pq)

                    response = get_chat_response(
                        st.session_state.chat_messages,
                        st.session_state.knowledge_text,
                    )
                    st.markdown("---")
                    st.markdown("### 🧠 AI Analysis")
                    st.markdown(response)

                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": response,
                        "chart_data": df.to_dict(orient="records") if not df.empty else None,
                        "chart_spec": {k: v for k, v in matched_pq.items() if k not in ("q", "icon", "sql")},
                    })
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
        else:
            with st.spinner("Analyzing..."):
                try:
                    response = get_chat_response(
                        st.session_state.chat_messages,
                        st.session_state.knowledge_text,
                    )
                    st.markdown(response)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": response}
                    )
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
