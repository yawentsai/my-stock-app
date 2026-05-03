import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import requests

# 1. 基礎設定與手機版規格優化
st.set_page_config(page_title="零股追蹤神器", layout="centered")
st_autorefresh(interval=60000, key="datarefresh") # 每分鐘更新

# --- LINE 通知核心函數 ---
def send_line_message(message):
    try:
        # 從 Secrets 讀取金鑰
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
    except Exception:
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
        st.write("連動 Google Sheets...")
        
    with st.expander("💸 實單庫存：賣出結算"):
        st.write("計算最終獲利入袋。")

    st.divider()
    with st.expander("🔔 加入/管理新聞追蹤"):
        st.write("設定關鍵字追蹤。")

    st.divider()
    st.subheader("🛠️ 通知系統測試")
    if st.button("🔔 測試發送 LINE 通知"):
        if send_line_message("✅ 零股追蹤神器：連線測試成功！"):
            st.success("通知已發送，請檢查手機！")
        else:
            st.error("發送失敗，請檢查 Secrets 設定。")

# --- 主頁面：🚀 零股追蹤神器 ---
st.title("🚀 零股追蹤神器")

# 2. 連結 Google Sheets 並讀取數據
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
except Exception:
    st.error("Google Sheets 連接失敗，請檢查 Secrets 中的 [connections.gsheets] 設定。")

# --- 🎯 真實資產結算看板 (手機版優化佈局) ---
st.markdown("### 🏦 真實資產結算看板")

# 假設數據 (這裡應根據妳的 Sheets 內容動態計算)
# 均價 1770, 持股 1 股, 假設現價 1810
cost_price = 1770
current_price = 1810
profit_rate = (current_price - cost_price) / cost_price

# 使用小卡片風格顯示指標
m1, m2 = st.columns(2)
m1.metric("總資產權益", "$100,000")
m2.metric("累計獲利", "$0", delta="0.00%")

m3, m4 = st.columns(2)
m3.metric("可用現金", "$98,230")
m4.metric("利用率", "1.8%")

st.divider()

# --- 🚦 停利執行監控區 ---
if profit_rate >= 0.02:
    st.warning(f"⚠️ 停利提醒：目前的持股獲利已達 {profit_rate:.2%}！")
    # 這裡可以加入自動發送邏輯，或維持手動測試
else:
    st.success("✅ 目前持股獲利尚未達 2% 停利標準，請繼續耐心持有。")

# --- 📊 實際預判勝率 ---
st.markdown("### 📊 實際預判勝率")
st.title("52.6%")
fig = px.pie(values=[74.1, 22.2, 3.7], names=['買進', '觀察', '追蹤'], hole=0.5)
fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
st.plotly_chart(fig, use_container_width=True)

# --- 📑 持股明細表 ---
st.markdown("#### 📋 實單持股明細")
# 這裡會顯示妳 Sheets 裡的雍智科技數據
st.dataframe(df, hide_index=True)
