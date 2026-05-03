import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re
from datetime import datetime
import yfinance as yf

st.set_page_config(page_title="交易戰情室 4.0", layout="wide")
st.title("💰 資產管理戰情室 4.0")

# 設定原始本金
TOTAL_CAPITAL = 100000

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 工具函數：抓取現價 ---
@st.cache_data(ttl=300)
def get_live_price(symbol):
    if not symbol: return None
    try:
        ticker = f"{symbol}.TW"
        data = yf.Ticker(ticker).fast_info
        return data['last_price']
    except:
        try:
            ticker = f"{symbol}.TWO"
            data = yf.Ticker(ticker).fast_info
            return data['last_price']
        except:
            return None

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚡ 快速買進登錄")
    with st.form("buy_form", clear_on_submit=True):
        st.caption("輸入買進明細 (將自動扣除 10 萬本金額度)")
        col1, col2 = st.columns(2)
        with col1: buy_name = st.text_input("名稱")
        with col2: buy_symbol = st.text_input("代號")
        
        buy_price = st.number_input("買入單價", min_value=0.0, step=0.1)
        buy_qty = st.number_input("買入股數", min_value=0, step=100, value=1000)
        
        submitted = st.form_submit_button("✅ 確認買進")
        
        if submitted and (buy_name or buy_symbol) and buy_price > 0:
            cost = buy_price * buy_qty
            new_row = pd.DataFrame([{
                "日期": datetime.now().strftime("%m/%d"),
                "標的": buy_name if buy_name else buy_symbol,
                "代號": buy_symbol, "操作": "買進",
                "成本": float(buy_price), "股數": int(buy_qty),
                "投入金額": cost, "漲跌%": 0.0,
                "盤前觀察": f"本金操作：投入 {cost} 元", "盤後紀錄": "持倉中"
            }])
            df_old = conn.read(ttl=0)
            conn.update(data=pd.concat([df_old, new_row], ignore_index=True))
            st.cache_data.clear()
            st.rerun()

    if st.button("🗑️ 清空資料庫"):
        conn.update(data=pd.DataFrame(columns=["日期", "標的", "代號", "操作", "成本", "股數", "投入金額", "漲跌%", "盤前觀察", "盤後紀錄"]))
        st.cache_data.clear()
        st.rerun()

# --- 主畫面顯示 ---
try:
    df = conn.read(ttl=0).dropna(subset=['標的'])
    # 確保欄位存在
    for col in ['成本', '股數', '投入金額']:
        if col not in df.columns: df[col] = 0.0
    
    # 1. 持倉計算
    holdings = df[df['盤後紀錄'] == "持倉中"].copy()
    
    # 2. 資金看板
    used_capital = holdings['投入金額'].sum()
    remaining_capital = TOTAL_CAPITAL - used_capital
    
    st.subheader("🏦 10 萬本金使用狀況")
    c1, c2, c3 = st.columns(3)
    c1.metric("已投入資金", f"${used_capital:,.0f}")
    c2.metric("剩餘可用資金", f"${remaining_capital:,.0f}")
    c3.metric("資金利用率", f"{(used_capital/TOTAL_CAPITAL)*100:.1f}%")

    if not holdings.empty:
        st.divider()
        st.subheader("📈 即時持倉盈虧 (TWD)")
        
        # 計算每檔盈虧
        plot_data = []
        total_unrealized_profit = 0
        
        cols = st.columns(3)
        for i, (idx, row) in enumerate(holdings.iterrows()):
            current_p = get_live_price(row['代號'])
            if current_p:
                profit_twd = (current_price - row['成本']) * row['股數']
                total_unrealized_profit += profit_twd
                plot_data.append({"標的": row['標的'], "損益": profit_twd})
                
                with cols[i % 3]:
                    st.markdown(f"""
                    <div style="padding:10px; border-radius:10px; border-left:5px solid {'#ef5350' if profit_twd>0 else '#26a69a'}; background:#f8f9fa;">
                        <b>{row['標的']}</b><br>
                        <small>盈虧：</small> <span style="color:{'#ef5350' if profit_twd>0 else '#26a69a'}; font-weight:bold;">${profit_twd:,.0f}</span>
                    </div>
                    """, unsafe_allow_html=True)

        # 3. 盈虧貢獻圓餅圖
        st.divider()
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.write("📊 持倉損益分佈")
            if plot_data:
                pdf = pd.DataFrame(plot_data)
                # 圓餅圖只顯示獲利部分的分佈，或是用長條圖顯示正負盈虧
                fig_profit = px.pie(pdf, values=pdf['損益'].abs(), names='標的', hole=0.4,
                                   title="各標的損益貢獻比 (絕對值)")
                st.plotly_chart(fig_profit, use_container_width=True)
        
        with col_right:
            total_return_rate = (total_unrealized_profit / TOTAL_CAPITAL) * 100
            st.metric("💰 帳戶總盈虧 (TWD)", f"${total_unrealized_profit:,.0f}", f"{total_return_rate:.2f}%")
            
    st.divider()
    st.write("📋 原始交易清單", df)

except Exception as e:
    st.info("請透過左側表單輸入買進標的。")
