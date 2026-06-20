import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import requests
import re

# 1. 基礎設定
st.set_page_config(page_title="投資整合系統", layout="wide")

# --- 側邊欄切換器 ---
st.sidebar.header("🕹️ 功能模組")
app_mode = st.sidebar.radio("選擇系統", ["🚀 零股追蹤神器", "📡 籌碼預警監控"])

# --- CSS 注入 ---
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

# --- 輔助函數 ---
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

# --- 模組：籌碼預警系統 ---
def run_chip_monitor():
    st.title("📡 籌碼預警監控")
    st.markdown("---")
    st.subheader("💡 核心關注：低軌衛星題材")
    st.info("佳邦 (6284) 分析：\n1. 被動元件補漲期待\n2. 本益比相對低\n3. SpaceX 低軌衛星題材")
    st.warning("Nok 分析：\n1. 隨 SpaceX 上市同時段表現\n2. 同屬於低軌衛星供應鏈")

# --- 模組：零股追蹤神器 ---
def run_zero_stock_app():
    # 這是你原先穩定的邏輯
    st.title("🚀 零股追蹤神器")
    st_autorefresh(interval=60000, limit=1000, key="global_v87_final")
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 這裡請貼上你原先所有的資料庫讀取、處理、Dashboard 顯示邏輯
    # (為了避免過長，這裡只展示架構，請將你原先那一大段程式碼原封不動貼在這裡即可)
    st.write("零股系統載入成功。")

# --- 執行邏輯 ---
if app_mode == "🚀 零股追蹤神器":
    run_zero_stock_app()
else:
    run_chip_monitor()
