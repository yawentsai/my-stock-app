import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import requests
import re

# --- 基礎設定 ---
st.set_page_config(page_title="投資整合系統", layout="wide")

# --- 側邊欄切換 ---
st.sidebar.header("🕹️ 功能模組")
app_mode = st.sidebar.radio("選擇系統", ["🚀 零股追蹤神器", "📡 籌碼預警監控"])

# --- CSS 樣式 ---
st.markdown("""
    <style>
    .dashboard-grid { display: grid; grid-template-columns: repeat(3, 1fr) !important; gap: 8px !important; margin-bottom: 20px; }
    .metric-card { background: #f8f9fa; padding: 12px 5px !important; border-radius: 8px; text-align: center; border: 1px solid #ddd; }
    .metric-label { font-size: 0.8rem; color: #555; margin-bottom: 4px; }
    .metric-value { font-size: 1.15rem; font-weight: bold; }
    section[data-testid="stSidebar"] .stExpander { border: 1px solid #eee !important; border-radius: 8px !important; margin-bottom: 12px !important; }
    .status-box { padding: 12px; border-radius: 8px; margin-bottom: 20px; text-align: center; font-size: 0.95rem; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# --- 函數區 ---
def format_list_text(text):
    if not isinstance(text, str) or not text.strip(): return ""
    text = text.replace('\n', '<br>')
    text = re.sub(r'(?<!^)(?<!<br>)\s*(\b\d+\.\s*)', r'<br>\1', text)
    return f'<div style="padding-left: 1.4em; text-indent: -1.4em; margin-top: 4px;">{text}</div>'

def send_line_message(message):
    try:
        token = st.secrets["LINE_CHANNEL_ACCESS_TOKEN"]
        user_id = st.secrets["LINE_USER_ID"]
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}
        return requests.post(url, headers=headers, json=payload).status_code == 200
    except: return False

@st.cache_data(ttl=60)
def get_live_price(symbol):
    try:
        ticker = f"{symbol}.TW"
        return yf.Ticker(ticker).fast_info['last_price']
    except:
        try: return yf.Ticker(f"{symbol}.TWO").fast_info['last_price']
        except: return None

# --- 籌碼預警系統模組 ---
def run_chip_monitor():
    st.title("📡 籌碼預警監控")
    st.markdown("---")
    st.subheader("💡 低軌衛星概念股追蹤")
    st.write("當前監控清單：**佳邦 (6284)**、**Nok**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 佳邦 (6284)\n- **狀態**：挑戰10日線/5日線觀察\n- **邏輯**：低軌衛星佈局，華新集團背景。")
    with col2:
        st.warning("### Nok\n- **狀態**：站上5日線，趨勢強勢\n- **邏輯**：SpaceX 概念供應鏈。")

# --- 零股追蹤神器模組 ---
def run_zero_stock_app():
    # 此處貼入你原有的完整零股追蹤程式邏輯
    # (從 conn = st.connection("gsheets", type=GSheetsConnection) 開始)
    st.title("🚀 零股追蹤神器")
    st_autorefresh(interval=60000, limit=1000, key="global_v87_final")
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # [貼入剩下的邏輯...]
    st.write("零股系統已載入。")

# --- 主邏輯切換 ---
if app_mode == "🚀 零股追蹤神器":
    run_zero_stock_app()
else:
    run_chip_monitor()
