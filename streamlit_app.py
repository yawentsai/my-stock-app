import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import yfinance as yf

st.set_page_config(page_title="交易戰情室 5.4", layout="wide")
st.title("🎯 交易戰情室 5.4 (手機排版優化版)")

# 💡 初始本金設定
INITIAL_CAPITAL = 100000

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

# --- 讀取與初始化資料庫 ---
try:
    existing_df = conn.read(ttl=0)
    required_cols = ['日期', '標的', '代號', '操作', '成本', '股數', '投入金額', '漲跌%', '盤前觀察', '盤後紀錄', '賣出價', '實現損益']
    for col in required_cols:
        if col not in existing_df.columns:
            existing_df[col] = 0.0 if col in ['成本', '股數', '投入金額', '漲跌%', '賣出價', '實現損益'] else ""
except Exception:
    existing_df = pd.DataFrame(columns=['日期', '標的', '代號', '操作', '成本', '股數', '投入金額', '漲跌%', '盤前觀察', '盤後紀錄', '賣出價', '實現損益'])

for col in ['成本', '股數', '投入金額', '漲跌%', '賣出價', '實現損益']:
    existing_df[col] = pd.to_numeric(existing_df[col], errors='coerce').fillna(0.0)

# --- 側邊欄：實單操作 ---
with st.sidebar:
    st.header("⚡ 實單操作區")
    
    with st.expander("🛒 買進/初始化持股", expanded=True):
        with st.form("buy_form", clear_on_submit=True):
            st.caption("輸入現有持股時，請填寫當時的『真實平均成本』")
            init_date = st.date_input("買進日期", value=date.today())
            col1, col2 = st.columns(2)
            with col1: buy_name = st.text_input("名稱 (如: 晶技)")
            with col2: buy_symbol = st.text_input("代號 (如: 2449)")
            buy_price = st.number_input("買入均價*", min_value=0.0, step=0.1)
            buy_qty = st.number_input("持有股數*", min_value=0, step=100, value=1000)
            buy_obs = st.text_area("備註 (如：期初持有、買進理由)")
            
            if st.form_submit_button("✅ 確認加入庫存") and (buy_name or buy_symbol) and buy_price > 0 and buy_qty > 0:
                name_val = buy_name.strip() if buy_name.strip() else buy_symbol.strip()
                cost = buy_price * buy_qty
                try:
                    new_row = pd.DataFrame([{
                        "日期": init_date.strftime("%m/%d"), "標的": name_val, "代號": buy_symbol.strip(),
                        "操作": "買進", "成本": float(buy_price), "股數": int(buy_qty), "投入金額": cost, 
                        "漲跌%": 0.0, "盤前觀察": buy_obs.replace('\n', ' '), "盤後紀錄": "實單持倉中",
                        "賣出價": 0.0, "實現損益": 0.0
                    }])
                    conn.update(data=pd.concat([existing_df, new_row], ignore_index=True))
                    st.cache_data.clear()
                    st.success(f"🎉 {name_val} 已加入庫存監控！")
                    st.rerun()
                except Exception as e:
                    st.error(f"寫入失敗: {str(e)}")

    with st.expander("💸 賣出登錄 (出場結算)"):
        active_holdings = existing_df[(existing_df['操作'] == '買進') & (existing_df['盤後紀錄'] == '實單持倉中')]
        if not active_holdings.empty:
            with st.form("sell_form", clear_on_submit=True):
                options = active_holdings.apply(lambda x: f"{x['日期']} - {x['標的']} (成本: {x['成本']})", axis=1).tolist()
                selected_sell = st.selectbox("選擇要賣出的持倉", options)
                sell_price = st.number_input("賣出單價*", min_value=0.0, step=0.1)
                sell_note = st.text_input("出場檢討 (選填)")
                
                if st.form_submit_button("💰 確認賣出結算") and sell_price > 0:
                    sel_date, sel_name_cost = selected_sell.split(" - ", 1)
                    sel_name = sel_name_cost.split(" (")[0]
                    idx = existing_df[(existing_df['日期'] == sel_date) & (existing_df['標的'] == sel_name) & (existing_df['盤後紀錄'] == '實單持倉中')].index[0]
                    cost_p = existing_df.at[idx, '成本']
                    qty = existing_df.at[idx, '股數']
                    real_pnl = (sell_price - cost_p) * qty
                    existing_df.at[idx, '賣出價'] = float(sell_price)
                    existing_df.at[idx, '實現損益'] = float(real_pnl)
                    existing_df.at[idx, '漲跌%'] = ((sell_price - cost_p) / cost_p) * 100
                    existing_df.at[idx, '盤後紀錄'] = f"已出場 ({sell_note})" if sell_note else "已出場"
                    conn.update(data=existing_df)
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.info("目前沒有持倉。")

    st.divider()
    st.header("📝 訓練預判工作區")
    with st.expander("🌅 Step 1: 盤前計畫"):
        with st.form("pre_market_form", clear_on_submit=True):
            log_date = st.text_input("日期", value=datetime.now().strftime("%m/%d"))
            log_action = st.selectbox("動作標記", ["觀察", "✅ 買進"])
            log_name = st.text_input("標的名稱 (必填)*")
            log_pre = st.text_area("盤前觀點")
            if st.form_submit_button("🚀 送出計畫") and log_name.strip():
                new_log = pd.DataFrame([{"日期": log_date, "標的": log_name.strip(), "代號": "", "操作": "買進" if "買進" in log_action else "觀察", "成本": 0.0, "股數": 0, "投入金額": 0.0, "漲跌%": 0.0, "盤前觀察": log_pre.replace('\n', ' '), "盤後紀錄": "⏳ 等待盤後更新...", "賣出價": 0.0, "實現損益": 0.0}])
                conn.update(data=pd.concat([existing_df, new_log], ignore_index=True))
                st.cache_data.clear()
                st.rerun()

    with st.expander("🌇 Step 2: 盤後更新"):
        pending = existing_df[existing_df['盤後紀錄'] == "⏳ 等待盤後更新..."]
        if not pending.empty:
            with st.form("post_market_form", clear_on_submit=True):
                opts = pending.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1).tolist()
                sel_opt = st.selectbox("更新標的", opts)
                log_post = st.text_area("實際狀況與回饋")
                log_pct = st.number_input("今日漲跌幅 %", value=0.0, step=0.1)
                if st.form_submit_button("💾 儲存結果"):
                    sd, sn = sel_opt.split(" - ", 1)
                    idx = existing_df[(existing_df['日期'] == sd) & (existing_df['標的'] == sn) & (existing_df['盤後紀錄'] == "⏳ 等待盤後更新...")].index[0]
                    existing_df.at[idx, '盤後紀錄'] = log_post.replace('\n', ' ')
                    existing_df.at[idx, '漲跌%'] = float(log_pct)
                    conn.update(data=existing_df)
                    st.cache_data.clear()
                    st.rerun()
                    
    st.divider()
    with st.expander("🗑️ 刪除歷史資料"):
        date_range = st.date_input("選擇日期區間", value=[])
        if st.button("🚨 確認刪除選定區間") and len(date_range) == 2:
            def is_in_range(d_str):
                try:
                    d = datetime.strptime(d_str, "%m/%d").replace(year=datetime.now().year).date()
                    return date_range[0] <= d <= date_range[1]
                except: return False
            df_to_keep = existing_df[~existing_df['日期'].apply(is_in_range)]
            conn.update(data=df_to_keep)
            st.cache_data.clear()
            st.rerun()

# --- 主畫面顯示 ---
try:
    df = existing_df.dropna(subset=['標的']).copy()
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    
    if not df.empty:
        # --- 數據計算 ---
        total_realized_pnl = df['實現損益'].sum()
        active_df = df[(df['操作'] == '買進') & (df['盤後紀錄'] == '實單持倉中')]
        used_capital = active_df['投入金額'].sum()
        
        total_unrealized_pnl = 0
        active_holdings_data = []
        ready_to_sell = []
        
        for i, (idx, row) in enumerate(active_df.iterrows()):
            curr_p = get_live_price(row['代號'])
            if curr_p:
                p_pct = ((curr_p - row['成本']) / row['成本']) * 100
                p_twd = (curr_p - row['成本']) * row['股數']
                total_unrealized_pnl += p_twd
                active_holdings_data.append({
                    '日期': row['日期'], '標的': row['標的'], '代號': row['代號'], 
                    '成本': row['成本'], '股數': row['股數'], '投入金額': row['投入金額'],
                    '現價': curr_p, '漲跌%': p_pct, '損益TWD': p_twd
                })
                if p_pct >= 10: ready_to_sell.append(f"{row['標的']} (+{p_pct:.1f}%)")
                    
        total_profit = total_realized_pnl + total_unrealized_pnl
        current_total_equity = INITIAL_CAPITAL + total_profit
        cash_pool = INITIAL_CAPITAL + total_realized_pnl
        rem_capital = cash_pool - used_capital
        util_rate = (used_capital / cash_pool) * 100 if cash_pool > 0 else 0

        # --- 💡 全新：緊湊型手機網格看板 ---
        st.markdown("### 🏦 真實資產結算看板")
        
        profit_color = "#1b5e20" if total_profit >= 0 else "#b71c1c"
        profit_bg = "#e8f5e9" if total_profit >= 0 else "#ffebee"
        
        dashboard_html = f"""
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 20px;">
            <div style="background: #f8f9fa; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #e0e0e0;">
                <div style="font-size: 0.75rem; color: #555;">總資產權益</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: #222;">${current_total_equity:,.0f}</div>
            </div>
            <div style="background: {profit_bg}; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #e0e0e0;">
                <div style="font-size: 0.75rem; color: {profit_color};">🎯 累計獲利</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: {profit_color};">${total_profit:,.0f}</div>
            </div>
            <div style="background: #f8f9fa; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #e0e0e0;">
                <div style="font-size: 0.75rem; color: #555;">📈 ROI</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: #222;">{(total_profit/INITIAL_CAPITAL)*100:.2f}%</div>
            </div>
            <div style="background: #fff3e0; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #e0e0e0;">
                <div style="font-size: 0.75rem; color: #e65100;">已投入資金</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: #e65100;">${used_capital:,.0f}</div>
            </div>
            <div style="background: #f8f9fa; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #e0e0e0;">
                <div style="font-size: 0.75rem; color: #555;">可用現金</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: #222;">${rem_capital:,.0f}</div>
            </div>
            <div style="background: #f8f9fa; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #e0e0e0;">
                <div style="font-size: 0.75rem; color: #555;">資金利用率</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: #222;">{util_rate:.1f}%</div>
            </div>
        </div>
        """
        st.markdown(dashboard_html, unsafe_allow_html=True)

        if ready_to_sell:
            st.markdown(f"""
            <div style="padding: 12px; border-radius: 8px; background-color: #ffebee; border-left: 5px solid #ef5350; margin-bottom: 20px;">
                <h5 style="margin-top: 0; margin-bottom: 5px; color: #c62828;">🎯 停利警報：</h5>
                <p style="margin-bottom: 0; font-size: 14px; color: #b71c1c;">{', '.join(ready_to_sell)}</p>
            </div>
            """, unsafe_allow_html=True)

        # --- 頁籤 ---
        tab1, tab2, tab3 = st.tabs(["💼 實單持股明細", "📅 依【日期】盤後日誌", "🗂️ 依【個股】深度追蹤"])
        
        with tab1:
            if active_holdings_data:
                st.dataframe(pd.DataFrame(active_holdings_data)[['日期', '標的', '代號', '股數', '成本', '現價', '投入金額', '損益TWD']], use_container_width=True, hide_index=True)
            else: st.info("目前無持倉。")
                
        completed_df = df[~df['盤後紀錄'].isin(["⏳ 等待盤後更新...", "實單持倉中"])].copy()
        
        with tab2:
            if not completed_df.empty:
                completed_df['月份'] = completed_df['日期'].apply(lambda x: str(x).split('/')[0] + '月' if '/' in str(x) else '未知')
                for month in sorted(completed_df['月份'].unique(), reverse=True):
                    st.markdown(f"#### 🗓️ {month}")
                    m_df = completed_df[completed_df['月份'] == month]
                    for date_str in sorted(m_df['日期'].unique(), reverse=True):
                        d_df = m_df[m_df['日期'] == date_str]
                        with st.expander(f"📅 {date_str}"):
                            for _, row in d_df.iterrows():
                                action_badge = f"<span style='background-color:#ef5350; color:white; padding:2px 6px; border-radius:4px; font-size:0.8rem;'>{row['操作']}</span>"
                                result_color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "gray")
                                st.markdown(f"""
                                <div style="padding:8px; border-bottom:1px solid #eee;">
                                    {action_badge} <strong>{row['標的']}</strong> 
                                    <span style="color:{result_color}; float:right; font-weight:bold;">{row['漲跌%']}%</span><br>
                                    <span style="color:#666; font-size:0.85rem;">📝 {row['盤後紀錄']}</span>
                                </div>
                                """, unsafe_allow_html=True)
            else: st.info("尚無歷史日誌。")

        with tab3:
            if not completed_df.empty:
                for target in sorted(completed_df['標的'].unique()):
                    with st.expander(f"📌 {target}"):
                        t_df = completed_df[completed_df['標的'] == target].sort_values(by='日期', ascending=False)
                        for _, row in t_df.iterrows():
                            color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "#bdbdbd")
                            st.markdown(f"""
                            <div style="border-left:5px solid {color}; padding:10px; background:#f8f9fa; margin-bottom:10px;">
                                <b>{row['日期']} | {row['操作']} | <span style="color:{color};">{row['漲跌%']}%</span></b><br>
                                <div style="margin-top:6px; font-size:0.95rem;">
                                    <span style="color:#555;">🔍 <b>盤前：</b> {row['盤前觀察']}</span><br>
                                    <span style="color:#222;">📝 <b>盤後：</b> {row['盤後紀錄']}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

        # 圓餅圖
        if not completed_df.empty:
            st.divider()
            st.markdown("### 🎯 歷史交易紀律比例")
            completed_df['動作標籤'] = completed_df['操作'].apply(lambda x: '買進' if x == '買進' else '未買進')
            fig = px.pie(completed_df, names='動作標籤', hole=0.4, color='動作標籤', color_discrete_map={'買進':'#2196f3', '未買進':'#bdbdbd'})
            st.plotly_chart(fig, use_container_width=True)

    else: st.info("資料庫目前為空。")
except Exception as e: st.info(f"載入中... ({e})")
