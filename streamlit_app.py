import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf

st.set_page_config(page_title="交易戰情室 4.4", layout="wide")
st.title("🎯 交易戰情室 4.4 (日夜雙軌作業版)")

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

# --- 讀取現有資料庫 ---
try:
    existing_df = conn.read(ttl=0)
    for col in ['日期', '標的', '代號', '操作', '成本', '股數', '投入金額', '漲跌%', '盤前觀察', '盤後紀錄']:
        if col not in existing_df.columns:
            existing_df[col] = 0.0 if col in ['成本', '股數', '投入金額', '漲跌%'] else ""
except Exception:
    existing_df = pd.DataFrame(columns=['日期', '標的', '代號', '操作', '成本', '股數', '投入金額', '漲跌%', '盤前觀察', '盤後紀錄'])

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚡ 實單買進登錄 (扣除本金)")
    with st.form("buy_form", clear_on_submit=True):
        st.caption("填寫此單將扣除本金額度並啟動即時監控")
        col1, col2 = st.columns(2)
        with col1: buy_name = st.text_input("名稱 (如: 晶技)")
        with col2: buy_symbol = st.text_input("代號 (如: 2449)")
        buy_price = st.number_input("買入單價*", min_value=0.0, step=0.1)
        buy_qty = st.number_input("買入股數*", min_value=0, step=100, value=1000)
        buy_obs = st.text_area("進場理由")
        submitted_buy = st.form_submit_button("✅ 確認買進")
        
        if submitted_buy and (buy_name or buy_symbol) and buy_price > 0 and buy_qty > 0:
            name_val = buy_name.strip() if buy_name.strip() else buy_symbol.strip()
            cost = buy_price * buy_qty
            try:
                new_row = pd.DataFrame([{
                    "日期": datetime.now().strftime("%m/%d"), "標的": name_val, "代號": buy_symbol.strip(),
                    "操作": "買進", "成本": float(buy_price), "股數": int(buy_qty), "投入金額": cost, 
                    "漲跌%": 0.0, "盤前觀察": buy_obs.replace('\n', ' '), "盤後紀錄": "實單持倉中"
                }])
                conn.update(data=pd.concat([existing_df, new_row], ignore_index=True))
                st.cache_data.clear()
                st.success(f"🎉 {name_val} 已加入實單監控！")
                st.rerun()
            except Exception as e:
                st.error(f"寫入失敗: {str(e)}")

    st.divider()
    
    # ==========================================
    # 🎯 全新設計：分離的日夜工作流
    # ==========================================
    st.header("📝 訓練預判工作區")
    
    # 🌅 Step 1: 盤前預判
    with st.expander("🌅 Step 1: 盤前預判 (早上填寫)", expanded=True):
        with st.form("pre_market_form", clear_on_submit=True):
            log_date = st.text_input("日期", value=datetime.now().strftime("%m/%d"))
            log_action = st.selectbox("動作標記", ["觀察", "✅ 買進"])
            log_name = st.text_input("標的名稱 (必填)*")
            log_pre = st.text_area("盤前觀點 / 觀察重點")
            
            submitted_pre = st.form_submit_button("🚀 送出盤前計畫")
            
            if submitted_pre:
                if log_name.strip():
                    new_log = pd.DataFrame([{
                        "日期": log_date, "標的": log_name.strip(), "代號": "",
                        "操作": "買進" if "買進" in log_action else "觀察", 
                        "成本": 0.0, "股數": 0, "投入金額": 0.0, "漲跌%": 0.0, 
                        "盤前觀察": log_pre.replace('\n', ' '), 
                        "盤後紀錄": "⏳ 等待盤後更新..." # 關鍵標記
                    }])
                    conn.update(data=pd.concat([existing_df, new_log], ignore_index=True))
                    st.cache_data.clear()
                    st.success(f"🌅 {log_name} 盤前計畫已記錄！")
                    st.rerun()
                else:
                    st.warning("請填寫標的名稱！")

    # 🌇 Step 2: 盤後更新
    with st.expander("🌇 Step 2: 盤後更新 (下午填寫)", expanded=True):
        # 尋找需要更新的標的
        pending_mask = existing_df['盤後紀錄'] == "⏳ 等待盤後更新..."
        pending_records = existing_df[pending_mask]
        
        if not pending_records.empty:
            with st.form("post_market_form", clear_on_submit=True):
                # 製作下拉選單選項 (日期 + 名稱)
                options = pending_records.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1).tolist()
                selected_option = st.selectbox("選擇要更新的標的", options)
                
                log_post = st.text_area("盤後實際狀況與回饋")
                log_pct = st.number_input("今日漲跌幅 % (如: 6.79, -1.6)", value=0.0, step=0.1)
                
                submitted_post = st.form_submit_button("💾 儲存盤後結果")
                
                if submitted_post:
                    # 解析選到的日期與名稱
                    sel_date, sel_name = selected_option.split(" - ", 1)
                    # 找出那一行的索引並更新
                    idx_to_update = existing_df[(existing_df['日期'] == sel_date) & 
                                                (existing_df['標的'] == sel_name) & 
                                                (existing_df['盤後紀錄'] == "⏳ 等待盤後更新...")].index[0]
                    
                    existing_df.at[idx_to_update, '盤後紀錄'] = log_post.replace('\n', ' ')
                    existing_df.at[idx_to_update, '漲跌%'] = float(log_pct)
                    
                    conn.update(data=existing_df)
                    st.cache_data.clear()
                    st.success(f"🌇 {sel_name} 盤後結果已統整完成！")
                    st.rerun()
        else:
            st.info("✅ 目前沒有需要盤後更新的標的。")

    st.divider()
    if st.button("🗑️ 一鍵清空舊資料庫"):
        empty_df = pd.DataFrame(columns=["日期", "標的", "代號", "操作", "成本", "股數", "投入金額", "漲跌%", "盤前觀察", "盤後紀錄"])
        conn.update(data=empty_df)
        st.cache_data.clear()
        st.rerun()

# --- 主畫面顯示 ---
try:
    df = existing_df.dropna(subset=['標的']).copy()
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    df = df[(df['標的'].str.len() <= 6) & (df['標的'].str.len() > 0)]
    df['漲跌%'] = pd.to_numeric(df['漲跌%'], errors='coerce').fillna(0.0)
    df['成本'] = pd.to_numeric(df['成本'], errors='coerce').fillna(0.0)

    if not df.empty:
        # ==========================================
        # 模塊 1：💰 本金與實單持倉監控
        # ==========================================
        monitor_df = df[(df['操作'] == '買進') & (df['成本'] > 0)].copy()
        st.markdown(f"### 💰 實單持倉與資金雷達 ({TOTAL_CAPITAL/10000:.0f}萬本金)")
        used_capital = monitor_df['投入金額'].sum() if not monitor_df.empty else 0
        rem_capital = TOTAL_CAPITAL - used_capital
        
        c1, c2, c3 = st.columns(3)
        c1.metric("已投入資金", f"${used_capital:,.0f}")
        c2.metric("剩餘可用資金", f"${rem_capital:,.0f}")
        c3.metric("本金利用率", f"{(used_capital/TOTAL_CAPITAL)*100:.1f}%")

        if not monitor_df.empty:
            plot_data = []
            total_unrealized = 0
            card_cols = st.columns(3)
            for i, (idx, row) in enumerate(monitor_df.iterrows()):
                current_price = get_live_price(row['代號'])
                if current_price:
                    profit_pct = ((current_price - row['成本']) / row['成本']) * 100
                    profit_twd = (current_price - row['成本']) * row['股數']
                    total_unrealized += profit_twd
                    plot_data.append({"標的": row['標的'], "損益(TWD)": profit_twd, "絕對值": abs(profit_twd), "狀態": "獲利" if profit_twd > 0 else "虧損"})
                    with card_cols[i % 3]:
                        st.markdown(f"""
                        <div style="padding:15px; background:white; border-radius:10px; border: 1px solid #ddd; border-left: 5px solid {'#ef5350' if profit_pct>=10 else '#2196f3'};">
                            <h4 style="margin:0;">{row['標的']}</h4>
                            <p style="margin:5px 0; color:gray; font-size:14px;">均價: ${row['成本']} | 現價: ${current_price:.2f}</p>
                            <h3 style="margin:0; color:{'#ef5350' if profit_pct>0 else '#26a69a'};">{'+' if profit_pct>0 else ''}{profit_pct:.2f}% (${profit_twd:,.0f})</h3>
                        </div>
                        """, unsafe_allow_html=True)
                        if profit_pct >= 10: st.error(f"🚨 **{row['標的']}** 已達 10% 停利目標！")
            
            if plot_data:
                st.write("")
                st.caption("🔻 實單持股損益貢獻度")
                pdf = pd.DataFrame(plot_data)
                fig_pnl = px.pie(pdf, values='絕對值', names='標的', hole=0.4, color='狀態',
                                 color_discrete_map={'獲利':'#ef5350', '虧損':'#26a69a'})
                fig_pnl.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                st.plotly_chart(fig_pnl, use_container_width=True)
        st.divider()

        # ==========================================
        # 模塊 2：🎯 歷史預判勝率與覆盤日誌
        # ==========================================
        st.markdown("### 🎯 歷史預判勝率與覆盤日誌")
        
        # 過濾掉還在等待盤後更新的資料，不列入勝率計算
        completed_df = df[df['盤後紀錄'] != "⏳ 等待盤後更新..."].copy()
        
        if not completed_df.empty:
            completed_df['預判結果'] = completed_df['漲跌%'].apply(lambda x: '獲利' if x > 0 else ('虧損' if x < 0 else '持平'))
            buy_df = completed_df[completed_df['操作'] == '買進']
            
            win_rate = (len(buy_df[buy_df['漲跌%'] > 0]) / len(buy_df) * 100) if len(buy_df) > 0 else 0
            st.metric("📊 實際買進預判勝率", f"{win_rate:.1f}%")
            
            if not buy_df.empty:
                fig_winrate = px.pie(buy_df, names='預判結果', hole=0.4, color='預判結果', 
                                     color_discrete_map={'獲利':'#ef5350', '虧損':'#26a69a', '持平':'#bdbdbd'})
                fig_winrate.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                st.plotly_chart(fig_winrate, use_container_width=True)
        else:
            st.info("尚無完成盤後更新的資料可計算勝率。")

        st.write("") 
        tab1, tab2 = st.tabs(["🗂️ 依【個股】深度追蹤", "📅 依【日期】盤後日誌"])
        with tab1:
            for target in sorted(df['標的'].unique()):
                t_df = df[df['標的'] == target].sort_values(by='日期', ascending=False)
                with st.expander(f"📌 {target} (總紀錄：{len(t_df)} 筆)"):
                    for _, row in t_df.iterrows():
                        color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "#bdbdbd")
                        if row['盤後紀錄'] == "⏳ 等待盤後更新...": color = "#ffb300" # 等待中顯示橘黃色
                        st.markdown(f"""
                        <div style="border-left:5px solid {color}; padding:10px; background:#f8f9fa; margin-bottom:10px;">
                            <b>{row['日期']} | {row['操作']} | <span style="color:{color};">{row['漲跌%']}%</span></b><br>
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
                    buy_count = len(d_df[d_df['操作'] == '買進'])
                    obs_count = len(d_df[d_df['操作'] == '觀察'])
                    with st.expander(f"📅 {date} (買進: {buy_count} 檔 | 觀察: {obs_count} 檔)", expanded=True if date == df['日期'].max() else False):
                        for _, row in d_df.iterrows():
                            action_badge = f"<span style='background-color:#ef5350; color:white; padding:2px 6px; border-radius:4px; font-size:0.8rem;'>買進</span>" if row['操作'] == '買進' else f"<span style='background-color:#bdbdbd; color:white; padding:2px 6px; border-radius:4px; font-size:0.8rem;'>觀察</span>"
                            result_color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "gray")
                            if row['盤後紀錄'] == "⏳ 等待盤後更新...": result_color = "#ffb300"
                            st.markdown(f"""
                            <div style="padding:8px; border-bottom:1px solid #eee;">
                                {action_badge} <strong>{row['標的']}</strong> 
                                <span style="color:{result_color}; float:right; font-weight:bold;">{row['漲跌%']}%</span><br>
                                <span style="color:#666; font-size:0.85rem;">📝 {row['盤後紀錄']}</span>
                            </div>
                            """, unsafe_allow_html=True)
    else:
        st.info("資料庫目前為空，請輸入資料。")
except Exception as e:
    st.info(f"系統啟動中... ({str(e)})")
