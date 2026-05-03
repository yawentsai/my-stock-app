import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import yfinance as yf

st.set_page_config(page_title="交易戰情室 5.6", layout="wide")
st.title("🎯 交易戰情室 5.6 (大字戰情看板版)")

# 💡 初始本金設定
INITIAL_CAPITAL = 100000

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 工具函數：抓取現價 ---
@st.cache_data(ttl=300)
def get_live_price(symbol):
    if not symbol or symbol == "": return None
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

# --- 讀取與初始化資料庫 ---
try:
    existing_df = conn.read(ttl=0)
    required_cols = ['日期', '標的', '代號', '操作', '成本', '股數', '投入金額', '漲跌%', '盤前觀察', '盤後紀錄', '賣出價', '實現損益']
    for col in required_cols:
        if col not in existing_df.columns:
            existing_df[col] = 0.0 if col in ['成本', '股數', '投入金額', '漲跌%', '賣出價', '實現損益'] else ""
except Exception:
    existing_df = pd.DataFrame(columns=['日期', '標的', '代號', '操作', '成本', '股數', '投入金額', '漲跌%', '盤前觀察', '盤後紀錄', '賣出價', '實現損益'])

# 強制轉型
for col in ['成本', '股數', '投入金額', '漲跌%', '賣出價', '實現損益']:
    existing_df[col] = pd.to_numeric(existing_df[col], errors='coerce').fillna(0.0)

# --- 側邊欄：實單操作 ---
with st.sidebar:
    st.header("⚡ 實單操作區")
    
    with st.expander("🛒 買進/初始化持股", expanded=True):
        with st.form("buy_form", clear_on_submit=True):
            st.caption("輸入現有持股時，請填寫『平均成本』")
            init_date = st.date_input("買進日期", value=date.today())
            col1, col2 = st.columns(2)
            with col1: buy_name = st.text_input("名稱")
            with col2: buy_symbol = st.text_input("代號")
            buy_price = st.number_input("買入均價*", min_value=0.0, step=0.1)
            buy_qty = st.number_input("持有股數*", min_value=0, step=1, value=100)
            buy_obs = st.text_area("進場備註")
            
            if st.form_submit_button("✅ 確認加入庫存"):
                if (buy_name or buy_symbol) and buy_price > 0:
                    name_val = buy_name.strip() if buy_name.strip() else buy_symbol.strip()
                    cost = buy_price * buy_qty
                    new_row = pd.DataFrame([{
                        "日期": init_date.strftime("%m/%d"), "標的": name_val, "代號": buy_symbol.strip(),
                        "操作": "買進", "成本": float(buy_price), "股數": int(buy_qty), "投入金額": cost, 
                        "漲跌%": 0.0, "盤前觀察": buy_obs.replace('\n', ' '), "盤後紀錄": "實單持倉中",
                        "賣出價": 0.0, "實現損益": 0.0
                    }])
                    conn.update(data=pd.concat([existing_df, new_row], ignore_index=True))
                    st.cache_data.clear()
                    st.rerun()

    with st.expander("💸 賣出結算"):
        active_holdings = existing_df[(existing_df['操作'] == '買進') & (existing_df['盤後紀錄'] == '實單持倉中')]
        if not active_holdings.empty:
            with st.form("sell_form", clear_on_submit=True):
                options = active_holdings.apply(lambda x: f"{x['日期']} - {x['標的']} (成本: {x['成本']})", axis=1).tolist()
                selected_sell = st.selectbox("選擇要賣出的持倉", options)
                sell_price = st.number_input("賣出單價*", min_value=0.0, step=0.1)
                sell_note = st.text_input("出場檢討")
                if st.form_submit_button("💰 確認賣出"):
                    sel_date, sel_name_cost = selected_sell.split(" - ", 1)
                    sel_name = sel_name_cost.split(" (")[0]
                    idx = existing_df[(existing_df['日期'] == sel_date) & (existing_df['標的'] == sel_name) & (existing_df['盤後紀錄'] == '實單持倉中')].index[0]
                    cost_p = existing_df.at[idx, '成本']
                    qty = existing_df.at[idx, '股數']
                    realized = (sell_price - cost_p) * qty
                    existing_df.at[idx, '賣出價'] = float(sell_price)
                    existing_df.at[idx, '實現損益'] = float(realized)
                    existing_df.at[idx, '漲跌%'] = ((sell_price - cost_p) / cost_p) * 100
                    existing_df.at[idx, '盤後紀錄'] = f"已出場 ({sell_note})" if sell_note else "已出場"
                    conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

# --- 主畫面顯示 ---
try:
    df = existing_df.dropna(subset=['標的']).copy()
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    
    # 數據計算
    total_realized_pnl = df['實現損益'].sum()
    active_df = df[(df['操作'] == '買進') & (df['盤後紀錄'] == '實單持倉中')]
    used_capital = active_df['投入金額'].sum()
    
    total_unrealized_pnl = 0
    active_holdings_data = []
    ready_to_sell = []
    
    for i, (idx, row) in enumerate(active_df.iterrows()):
        curr_p = get_live_price(row['代號'])
        p_pct = ((curr_p - row['成本']) / row['成本']) * 100 if curr_p else 0.0
        p_twd = (curr_p - row['成本']) * row['股數'] if curr_p else 0.0
        total_unrealized_pnl += p_twd
        active_holdings_data.append({
            '日期': row['日期'], '標的': row['標的'], '代號': row['代號'], 
            '成本': row['成本'], '股數': row['股數'], '投入金額': row['投入金額'],
            '現價': curr_p if curr_p else "假日/讀取中", 
            '漲跌%': p_pct, '損益TWD': p_twd
        })
        if p_pct >= 10: ready_to_sell.append(f"{row['標的']} (+{p_pct:.1f}%)")
                
    total_profit = total_realized_pnl + total_unrealized_pnl
    current_total_equity = INITIAL_CAPITAL + total_profit
    cash_pool = INITIAL_CAPITAL + total_realized_pnl
    rem_capital = cash_pool - used_capital
    util_rate = (used_capital / cash_pool) * 100 if cash_pool > 0 else 0

    # 1. 💡 強化版看板 (字體放大 1.5 倍)
    st.markdown("### 🏦 真實資產結算看板")
    
    profit_color = "#1b5e20" if total_profit >= 0 else "#b71c1c"
    profit_bg = "#e8f5e9" if total_profit >= 0 else "#ffebee"
    
    # 這裡調整了 font-size (從 0.7->1.05, 0.95->1.45) 並增加了 padding
    dashboard_html = f"""
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 20px;">
        <div style="background: #f8f9fa; padding: 15px 10px; border-radius: 8px; text-align: center; border: 1px solid #ddd;">
            <div style="font-size: 1.05rem; color: #555; margin-bottom: 5px;">總資產權益</div>
            <div style="font-size: 1.45rem; font-weight: bold; color: #222;">${current_total_equity:,.0f}</div>
        </div>
        <div style="background: {profit_bg}; padding: 15px 10px; border-radius: 8px; text-align: center; border: 1px solid #ddd;">
            <div style="font-size: 1.05rem; color: {profit_color}; margin-bottom: 5px;">🎯 累計獲利</div>
            <div style="font-size: 1.45rem; font-weight: bold; color: {profit_color};">${total_profit:,.0f}</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px 10px; border-radius: 8px; text-align: center; border: 1px solid #ddd;">
            <div style="font-size: 1.05rem; color: #555; margin-bottom: 5px;">📈 ROI</div>
            <div style="font-size: 1.45rem; font-weight: bold; color: #222;">{(total_profit/INITIAL_CAPITAL)*100:.2f}%</div>
        </div>
        <div style="background: #fff3e0; padding: 15px 10px; border-radius: 8px; text-align: center; border: 1px solid #ddd;">
            <div style="font-size: 1.05rem; color: #e65100; margin-bottom: 5px;">已投入資金</div>
            <div style="font-size: 1.45rem; font-weight: bold; color: #e65100;">${used_capital:,.0f}</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px 10px; border-radius: 8px; text-align: center; border: 1px solid #ddd;">
            <div style="font-size: 1.05rem; color: #555; margin-bottom: 5px;">可用現金</div>
            <div style="font-size: 1.45rem; font-weight: bold; color: #222;">${rem_capital:,.0f}</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px 10px; border-radius: 8px; text-align: center; border: 1px solid #ddd;">
            <div style="font-size: 1.05rem; color: #555; margin-bottom: 5px;">利用率</div>
            <div style="font-size: 1.45rem; font-weight: bold; color: #222;">{util_rate:.1f}%</div>
        </div>
    </div>
    """
    st.markdown(dashboard_html, unsafe_allow_html=True)

    if ready_to_sell: st.error(f"🎯 停利：{', '.join(ready_to_sell)}")

    # 2. 頁籤與內容
    t1, t2, t3 = st.tabs(["💼 實單持股明細", "📅 歷史日誌", "🗂️ 個股追蹤"])
    with t1:
        if active_holdings_data:
            st.dataframe(pd.DataFrame(active_holdings_data), use_container_width=True, hide_index=True)
        else: st.info("無持倉。")

    completed_df = df[~df['盤後紀錄'].str.contains("實單持倉中|⏳ 等待更新...", na=False)].copy()
    with t2:
        if not completed_df.empty:
            for m in sorted(completed_df['日期'].apply(lambda x: x.split('/')[0]).unique(), reverse=True):
                st.markdown(f"**🗓️ {m}月**")
                m_df = completed_df[completed_df['日期'].str.startswith(m)]
                for d in sorted(m_df['日期'].unique(), reverse=True):
                    with st.expander(f"📅 {d}"):
                        for _, r in m_df[m_df['日期']==d].iterrows():
                            st.write(f"{r['操作']} {r['標的']} ({r['漲跌%']}%)")
        else: st.info("無歷史日誌。")

    with t3:
        if not completed_df.empty:
            for t in sorted(completed_df['標的'].unique()):
                with st.expander(f"📌 {t}"): st.write(completed_df[completed_df['標的']==t])

except Exception as e: st.info(f"載入中... ({e})")
