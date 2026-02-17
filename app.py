"""
FoodFlow AI — Unified Multi-Page Streamlit Application
Single entry point for Dashboard, Chatbot, and Agentic Dashboard.
Run: streamlit run app.py --server.port 8501
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import streamlit as st

# ── Page Config (must be first Streamlit call) ──
st.set_page_config(
    page_title="FoodFlow AI — Food Waste Reduction Platform",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Ensure database exists ──
from database.db import DB_PATH, init_database, copy_db_for_page
if not os.path.exists(DB_PATH):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_database()

# ── Pre-copy DB for each page (eliminates DuckDB file-locking) ──
for _page in ("dashboard", "chatbot", "agentic"):
    copy_db_for_page(_page)

# ── Define pages ──
dashboard_page = st.Page("pages/1_dashboard.py", title="Dashboard", icon="📊", default=True)
chatbot_page = st.Page("pages/2_chatbot.py", title="AI Chatbot", icon="🤖")
agentic_page = st.Page("pages/3_agentic.py", title="Agentic Dashboard", icon="🧠")

pg = st.navigation(
    {
        "Analytics": [dashboard_page],
        "AI Tools": [chatbot_page, agentic_page],
    }
)

pg.run()
