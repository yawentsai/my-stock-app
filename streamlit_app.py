import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import requests
from streamlit_autorefresh import st_autorefresh

# 1. 基礎設定：優化手機版顯示與自動刷新
st.set_page_config(page_title="零股追蹤神器", layout="centered")
st_autorefresh(interval=60000, key="datarefresh") # 每 60 秒自動更新數據

# --- LINE 通知核心函數 ---
def send_line_message(message):
    try:
        # 從 Streamlit Secrets 安全讀取金鑰
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

# --- 側邊欄：系統控制與測試區 ---
with st.sidebar:
    st.markdown("⚡ # 系統控制區")
    with st.expander("🌅 Step 1: 盤前計畫"):
        st.info("檢查台積電 ADR 與美股半導體表現。")
    with st.expander("🌇 Step 2: 盤後統整"):
        st.info("記錄今日 AI 標的交易邏輯。")
    st.divider()
    with st.expander("🛒 實單庫存：買入/賣出"):
        st.write("連動 Google Sheets 數據...")
    with st.expander("🔔 加入/管理新聞追蹤"):
        st.write("設定關鍵字追蹤。")
    st.divider()
    st.subheader("🛠️ 通知系統測試")
    if st.button("🔔 測試發送 LINE 通知"):
        if send_line_message("✅ 零股追蹤神器：連線測試成功！"):
            st.success("通知已發送，請檢查手機！")
        else:
            st.error("發送失敗，請檢查 Secrets 設定。")

# --- 主頁面佈局 ---
st.title("🚀 零股追蹤神器")

# 2. 連結數據源
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
except Exception:
    st.error("Google Sheets 數據連接中斷，請確認 Secrets 設定。")

# --- 🎯 真實資產結算看板 (手機版 2x2 佈局) ---
st.markdown("### 🏦 真實資產結算看板")

# 此處數值應根據 df 動態計算，以下為妳目前畫面的顯示值
c1, c2 = st.columns(2)
c1.metric("總資產權益", "$100,000")
c2.metric("累計獲利", "$0", delta="0.00%")

c3, c4 = st.columns(2)
c3.metric("可用現金", "$98,230")
c4.metric("利用率", "1.8%")

st.divider()

# --- 🚦 停利執行監控 (針對雍智科技 6683 等標的) ---
# 假設妳目前的獲利已達 2.26%
profit_rate = 0.0226 

if profit_rate >= 0.02:
    st.warning(f"⚠️ 停利提醒：目前的持股獲利已達 {profit_rate:.2%}！")
    # 可選：若要自動通知，可解除下方註釋
    # send_line_message(f"🚨 停利指令：AI 標的獲利已達 {profit_rate:.2%}，請落實入袋為安！")
else:
    st.success("✅ 目前獲利尚未達 2% 標的，請依照紀律耐心持有。")

# --- 📊 實際預判勝率 ---
st.markdown("### 📊 實際預判勝率")
st.title("52.6%")
fig = px.pie(values=[74.1, 22.2, 3.7], names=['買進', '觀察', '追蹤'], hole=0.5)
fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True)
st.plotly_chart(fig, use_container_width=True)

# --- 📑 實單持股明細 ---
st.markdown("#### 📋 實單持股明細")
st.dataframe(df, hide_index=True)
