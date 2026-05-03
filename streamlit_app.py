import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import requests
from bs4 import BeautifulSoup
import urllib.parse

# 1. 基礎設定與手機版規格鎖定
st.set_page_config(page_title="零股追蹤神器", layout="wide")
st_autorefresh(interval=60000, key="datarefresh") # 每分鐘自動刷新

# --- LINE 通知核心函數 ---
def send_line_message(message):
    try:
        # 從 Streamlit Secrets 讀取金鑰
        token = st.secrets["LINE_CHANNEL_ACCESS_TOKEN"]
        user_id = st.secrets["LINE_USER_ID"]
        
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        payload = {
            "to": user_id,
            "messages": [{"type": "text", "text": message}]
        }
        response = requests.post(url, headers=headers, json=payload)
        return response.status_code == 200
    except Exception as e:
        return False

# --- 側邊欄系統控制區 ---
with st.sidebar:
    st.markdown("⚡ # 系統控制區")
    
    with st.expander("🌅 Step 1: 盤前計畫"):
        st.info("檢查美股表現與台積電 ADR 走勢。")
    
    with st.expander("🌇 Step 2: 盤後統整"):
        st.info("記錄今日交易邏輯與損益。")
        
    st.divider()
    
    with st.expander("🛒 實單庫存：買入登錄"):
        st.write("連動 Google Sheets 進行登錄...")
        
    with st.expander("💸 實單庫存：賣出結算"):
        st.write("計算最終獲利入袋。")

    st.divider()
    st.subheader("🛠️ 通知系統測試")
    if st.button("🔔 測試發送 LINE 通知"):
        if send_line_message("✅ 零股追蹤神器：連線測試成功！"):
            st.success("通知已發送，請檢查手機！")
        else:
            st.error("發送失敗，請檢查 Secrets 設定。")

# --- 主頁面：資產看板 ---
st.title("🚀 零股追蹤神器")

# 連結 Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read()

# 模擬計算獲利與顯示 (依據妳目前的持股狀況)
# 例如：雍智科技 (6683) 均價 1770
cost = 1770
current_price = 1810 # 假設現價
profit_rate = (current_price - cost) / cost

col1, col2, col3 = st.columns(3)
col1.metric("總資產權益", "$100,000")
col2.metric("累計獲利", "$0", delta="0.00%")
col3.metric("利用率", "1.8%")

# --- 自動監控停利機制 ---
if profit_rate >= 0.02:
    st.error(f"⚠️ 停利提醒：目前的持股獲利已達 {profit_rate:.2%}！")
    # 如果還沒發送過通知，可以在這裡呼叫函數
    # send_line_message(f"🚨 停利通知：雍智科技 (6683) 獲利已達 {profit_rate:.2%}，請執行入袋為安！")
else:
    st.success("✅ 目前持股獲利尚未達 2% 停利標準，請繼續耐心持有。")

# --- 預判勝率分析 ---
st.markdown("### 📊 實際預判勝率")
st.title("52.6%")
fig = px.pie(values=[74.1, 22.2, 3.7], names=['買進', '觀察', '追蹤'], hole=0.5)
st.plotly_chart(fig, use_container_width=True)
