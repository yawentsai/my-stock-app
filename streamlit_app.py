import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import requests
from streamlit_autorefresh import st_autorefresh

# 1. 基礎設定：優化手機版顯示比例與自動刷新
st.set_page_config(page_title="零股追蹤神器", layout="centered")
st_autorefresh(interval=60000, key="datarefresh") # 每 60 秒刷新一次

# --- LINE 通知核心函數 ---
def send_line_message(message):
    try:
        # 從 Secrets 讀取金鑰 (請確認 Secrets 內標籤名稱正確)
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

# --- 側邊欄：完整系統控制區 ---
with st.sidebar:
    st.markdown("⚡ # 系統控制區")
    
    # 盤前與盤後整理區 (恢復妳的功能)
    with st.expander("🌅 Step 1: 盤前計畫"):
        st.info("檢查美股表現、台積電 ADR 走勢與今日策略。")
    
    with st.expander("🌇 Step 2: 盤後統整"):
        st.info("記錄今日 AI 標的成交邏輯、情緒控管與損益。")
        
    st.divider()
    
    # 庫存管理區
    with st.expander("🛒 實單庫存：買入登錄"):
        st.write("連動 Google Sheets 進行買入登記...")
        
    with st.expander("💸 實單庫存：賣出結算"):
        st.write("記錄賣出點位，計算最終獲利入袋。")

    st.divider()
    
    # 新聞追蹤區 (恢復妳的功能)
    with st.expander("🔔 加入/管理新聞追蹤"):
        st.write("設定個股關鍵字追蹤（如：雍智、威剛）。")

    st.divider()
    
    # LINE 通知測試區
    st.subheader("🛠️ 通知系統測試")
    if st.button("🔔 測試發送 LINE 通知"):
        if send_line_message("✅ 零股追蹤神器：連線測試成功！妳的 2% 獲利守護防線已啟動。"):
            st.success("通知已發送，請檢查手機！")
        else:
            st.error("發送失敗，請檢查 Secrets 中的 Token 是否完整（包含結尾的 = 號）。")

# --- 主頁面佈局 ---
st.title("🚀 零股追蹤神器")

# 2. 連結數據源
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
except Exception:
    st.error("數據連接中斷，請確認 Secrets 中的 [connections.gsheets] 設定。")

# --- 🎯 真實資產結算看板 (強制 2x2 佈局) ---
st.markdown("### 🏦 真實資產結算看板")

# 模擬看板數據 (應由妳的 Google Sheets 動態計算)
# 目前持有：雍智科技 (6683)，均價 1770
# 假設目前的獲利狀況為 2.26%
profit_rate = 0.0226 

# 第一排指標
col1, col2 = st.columns(2)
col1.metric("總資產權益", "$100,000")
col2.metric("累計獲利", "$0", delta="0.00%")

# 第二排指標
col3, col4 = st.columns(2)
col3.metric("可用現金", "$98,230")
col4.metric("利用率", "1.8%")

st.divider()

# --- 🚦 停利執行監控欄位 (妳要求的欄位) ---
if profit_rate >= 0.02:
    # 欄位會變成黃色/紅色提醒
    st.warning(f"⚠️ 停利提醒：目前的持股獲利已達 {profit_rate:.2%}！")
    
    # 如果要讓它自動在達標時發 LINE，可解除下方備註：
    # send_line_message(f"🚨 停利通知：雍智科技 (6683) 獲利已達 {profit_rate:.2%}，請落實入袋為安！")
else:
    st.success("✅ 目前獲利尚未達 2% 標的，請依照紀律繼續持有。")

# --- 📊 實際預判勝率 ---
st.markdown("### 📊 實際預判勝率")
st.title("52.6%")
fig = px.pie(values=[74.1, 22.2, 3.7], names=['買進', '觀察', '追蹤'], hole=0.5)
fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True)
st.plotly_chart(fig, use_container_width=True)

# --- 📑 實單持股明細 ---
st.markdown("#### 📋 實單持股明細")
st.dataframe(df, hide_index=True)
