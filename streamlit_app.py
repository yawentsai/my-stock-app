import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf

st.set_page_config(page_title="交易戰情室 5.0", layout="wide")
st.title("🎯 交易戰情室 5.0 (持股明細版)")

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
    
    with st.expander("🛒 買進登錄 (進場)", expanded=True):
        with st.form("buy_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1: buy_name = st.text_input("名稱 (如: 晶技)")
            with col2: buy_symbol = st.text_input("代號 (如: 2449)")
            buy_price = st.number_input("買入單價*", min_value=0.0, step=0.1)
            buy_qty = st.number_input("買入股數*", min_value=0, step=100, value=1000)
            buy_obs = st.text_area("進場理由")
            
            if st.form_submit_button("✅ 確認買進") and (buy_name or buy_symbol) and buy_price > 0 and buy_qty > 0:
                name_val = buy_name.strip() if buy_name.strip() else buy_symbol.strip()
                cost = buy_price * buy_qty
                try:
                    new_row = pd.DataFrame([{
                        "日期": datetime.now().strftime("%m/%d"), "標的": name_val, "代號": buy_symbol.strip(),
                        "操作": "買進", "成本": float(buy_price), "股數": int(buy_qty), "投入金額": cost, 
                        "漲跌%": 0.0, "盤前觀察": buy_obs.replace('\n', ' '), "盤後紀錄": "實單持倉中",
                        "賣出價": 0.0, "實現損益": 0.0
                    }])
                    conn.update(data=pd.concat([existing_df, new_row], ignore_index=True))
                    st.cache_data.clear()
                    st.success(f"🎉 {name_val} 已買進建檔！")
                    st.rerun()
                except Exception as e:
                    st.error(f"寫入失敗: {str(e)}")

    with st.expander("💸 賣出登錄 (出場結算)", expanded=True):
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
                    
                    idx_to_update = existing_df[(existing_df['日期'] == sel_date) & 
                                                (existing_df['標的'] == sel_name) & 
                                                (existing_df['盤後紀錄'] == '實單持倉中')].index[0]
                    
                    cost_price = existing_df.at[idx_to_update, '成本']
                    qty = existing_df.at[idx_to_update, '股數']
                    realized_pnl = (sell_price - cost_price) * qty
                    pct_change = ((sell_price - cost_price) / cost_price) * 100
                    
                    existing_df.at[idx_to_update, '賣出價'] = float(sell_price)
                    existing_df.at[idx_to_update, '實現損益'] = float(realized_pnl)
                    existing_df.at[idx_to_update, '漲跌%'] = float(pct_change)
                    existing_df.at[idx_to_update, '盤後紀錄'] = f"已出場 ({sell_note})" if sell_note else "已出場"
                    
                    conn.update(data=existing_df)
                    st.cache_data.clear()
                    st.success(f"💰 {sel_name} 已結算！實現損益: ${realized_pnl:,.0f}")
                    st.rerun()
        else:
            st.info("目前沒有持倉部位可供賣出。")

    st.divider()
    
    # --- 訓練預判區 ---
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
        else:
            st.info("✅ 無待更新標的。")

    st.divider()
    
    st.header("⚙️ 資料庫管理")
    with st.expander("🗑️ 刪除歷史資料 (指定區間)", expanded=False):
        if not existing_df.empty:
            unique_dates = sorted(existing_df['日期'].unique())
            st.write(f"<small>目前資料庫日期範圍：{unique_dates[0]} ~ {unique_dates[-1]}</small>", unsafe_allow_html=True)
            
        date_range = st.date_input("選擇要刪除的日期區間", value=[])
        if st.button("🚨 確認刪除選定區間"):
            if len(date_range) == 2:
                start_date, end_date = date_range[0], date_range[1]
                def is_in_range(d_str):
                    try:
                        d = datetime.strptime(d_str, "%m/%d").replace(year=datetime.now().year).date()
                        return start_date <= d <= end_date
                    except: return False
                
                keep_mask = ~existing_df['日期'].apply(is_in_range)
                df_to_keep = existing_df[keep_mask]
                deleted_count = len(existing_df) - len(df_to_keep)
                conn.update(data=df_to_keep)
                st.cache_data.clear()
                st.success(f"✅ 已成功刪除 {deleted_count} 筆區間內的資料！")
                st.rerun()
            else:
                st.warning("⚠️ 操作失敗：請在上方日曆點選「兩個日期」形成區間。")
                
        st.write("---")
        if st.button("💣 徹底清空全部資料庫"):
            conn.update(data=pd.DataFrame(columns=required_cols))
            st.cache_data.clear()
            st.rerun()

# --- 主畫面顯示 ---
try:
    df = existing_df.dropna(subset=['標的']).copy()
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    df = df[(df['標的'].str.len() <= 6) & (df['標的'].str.len() > 0)]

    if not df.empty:
        # ==========================================
        # 模塊 1：💰 總資產與財務報表監控
        # ==========================================
        total_realized_pnl = df['實現損益'].sum()
        active_df = df[(df['操作'] == '買進') & (df['盤後紀錄'] == '實單持倉中')]
        used_capital = active_df['投入金額'].sum() if not active_df.empty else 0
        
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
                if p_pct >= 10:
                    ready_to_sell.append(f"{row['標的']} (+{p_pct:.1f}%)")
                    
        total_profit = total_realized_pnl + total_unrealized_pnl
        current_total_equity = INITIAL_CAPITAL + total_profit
        cash_pool = INITIAL_CAPITAL + total_realized_pnl
        rem_capital = cash_pool - used_capital
        utilization_rate = (used_capital / cash_pool) * 100 if cash_pool > 0 else 0

        st.markdown("### 🏦 真實資產結算看板")
        c1, c2, c3 = st.columns(3)
        c1.metric("總資產權益 (含未實現)", f"${current_total_equity:,.0f}")
        c2.metric("🎯 累計總獲利 (金額)", f"${total_profit:,.0f}", f"已結算: ${total_realized_pnl:,.0f} | 帳面: ${total_unrealized_pnl:,.0f}")
        c3.metric("📈 總報酬率 (ROI)", f"{(total_profit/INITIAL_CAPITAL)*100:.2f}%")
        
        st.write("") 
        c4, c5, c6 = st.columns(3)
        c4.metric("已投入資金 (持倉成本)", f"${used_capital:,.0f}")
        c5.metric("剩餘可用現金", f"${rem_capital:,.0f}")
        c6.metric("本金利用率", f"{utilization_rate:.1f}%")

        st.write("") 
        if not active_df.empty:
            if ready_to_sell:
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 8px; background-color: #ffebee; border-left: 5px solid #ef5350; margin-bottom: 20px;">
                    <h4 style="margin-top: 0; color: #c62828;">🎯 停利達標警報：有 {len(ready_to_sell)} 檔股票可結算出場！</h4>
                    <p style="margin-bottom: 0; font-size: 16px; color: #b71c1c;"><b>👉 可賣出清單：</b> {', '.join(ready_to_sell)}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="padding: 15px; border-radius: 8px; background-color: #f8f9fa; border-left: 5px solid #bdbdbd; margin-bottom: 20px;">
                    <p style="margin: 0; color: #555; font-size: 16px;">🎯 <b>停利監控：</b> 目前尚無獲利達 10% 的持股，請耐心等候主力抬轎。</p>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("#### 📡 即時持倉雷達")
            card_cols = st.columns(3)
            for i, data in enumerate(active_holdings_data):
                with card_cols[i % 3]:
                    st.markdown(f"""
                    <div style="padding:15px; background:white; border-radius:10px; border: 1px solid #ddd; border-left: 5px solid {'#ef5350' if data['漲跌%']>=10 else '#2196f3'};">
                        <h4 style="margin:0;">{data['標的']} ({data['代號']})</h4>
                        <p style="margin:5px 0; color:gray; font-size:14px;">均價: ${data['成本']} | 現價: ${data['現價']:.2f}</p>
                        <h3 style="margin:0; color:{'#ef5350' if data['漲跌%']>0 else '#26a69a'};">{'+' if data['漲跌%']>0 else ''}{data['漲跌%']:.2f}% (${data['損益TWD']:,.0f})</h3>
                    </div>
                    """, unsafe_allow_html=True)
        st.divider()

        # ==========================================
        # 模塊 2：🎯 歷史預判與覆盤日誌
        # ==========================================
        st.markdown("### 🎯 歷史預判與覆盤日誌")
        completed_df = df[~df['盤後紀錄'].isin(["⏳ 等待盤後更新...", "實單持倉中"])].copy()
        
        if not completed_df.empty:
            b_df = completed_df[completed_df['操作'] == '買進']
            win_r = (len(b_df[b_df['漲跌%'] > 0]) / len(b_df) * 100) if len(b_df) > 0 else 0
            
            completed_df['動作標籤'] = completed_df['操作'].apply(lambda x: '買進' if x == '買進' else '未買進')
            
            c_w1, c_w2 = st.columns([1, 2])
            with c_w1:
                st.metric("📊 實際買進預判勝率", f"{win_r:.1f}%")
            with c_w2:
                fig = px.pie(completed_df, names='動作標籤', hole=0.4, color='動作標籤', 
                             color_discrete_map={'買進':'#ef5350', '未買進':'#bdbdbd'})
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200)
                st.plotly_chart(fig, use_container_width=True)

        st.write("") 
        # --- 全新加入：三頁籤設計 ---
        tab1, tab2, tab3 = st.tabs(["🗂️ 依【個股】深度追蹤", "📅 依【日期】盤後日誌", "💼 實單持股明細"])
        
        with tab1:
            for target in sorted(df['標的'].unique()):
                t_df = df[df['標的'] == target].sort_values(by='日期', ascending=False)
                with st.expander(f"📌 {target} (紀錄：{len(t_df)} 筆)"):
                    for _, row in t_df.iterrows():
                        color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "#bdbdbd")
                        status_str = f"賣出結算價: ${row['賣出價']} (損益: ${row['實現損益']:,.0f})" if row['賣出價'] > 0 else "未結算/預判"
                        st.markdown(f"""
                        <div style="border-left:5px solid {color}; padding:10px; background:#f8f9fa; margin-bottom:10px;">
                            <b>{row['日期']} | {row['操作']} | <span style="color:{color};">{row['漲跌%']}%</span></b><br>
                            <small style="color:gray;">{status_str}</small>
                            <div style="margin-top:6px; font-size:0.95rem;">
                                <span style="color:#555;">🔍 <b>盤前：</b> {row['盤前觀察']}</span><br>
                                <span style="color:#222;">📝 <b>盤後：</b> {row['盤後紀錄']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

        with tab2:
            df['月份'] = df['日期'].apply(lambda x: str(x).split('/')[0] + '月' if '/' in str(x) else '未知')
            def sort_month(m_str):
                try: return int(m_str.replace('月', ''))
                except: return 0
            for month in sorted(df['月份'].unique(), key=sort_month, reverse=True):
                st.markdown(f"#### 🗓️ {month}")
                m_df = df[df['月份'] == month]
                for date in sorted(m_df['日期'].unique(), reverse=True):
                    d_df = m_df[m_df['日期'] == date]
                    with st.expander(f"📅 {date}", expanded=True if date == df['日期'].max() else False):
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
                            
        # --- 全新第三頁籤內容 ---
        with tab3:
            st.markdown("#### 💼 實單持股庫存明細")
            if active_holdings_data:
                # 建立要顯示的 DataFrame，並將欄位名稱改得更符合財務邏輯
                holdings_df = pd.DataFrame(active_holdings_data)
                display_df = holdings_df[['日期', '標的', '代號', '股數', '成本', '現價', '投入金額', '損益TWD']].copy()
                display_df.columns = ['買進日期', '標的名稱', '股票代號', '持有股數', '平均成本', '即時現價', '投入本金', '目前損益']
                
                # 在 Streamlit 中完美呈現表格
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("目前無正在持有的實單紀錄。")
                
    else:
        st.info("資料庫目前為空。")
except Exception as e:
    st.info(f"系統載入中... ({str(e)})")
