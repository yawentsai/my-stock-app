import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re
from datetime import datetime
import yfinance as yf

st.set_page_config(page_title="交易戰情室 4.1", layout="wide")
st.title("🎯 交易戰情室 4.1 (雙棲旗艦版)")

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
    st.header("⚡ 快速買進登錄 (實單)")
    with st.form("buy_form", clear_on_submit=True):
        st.caption("填寫此單將扣除 10 萬本金額度並啟動即時監控")
        col1, col2 = st.columns(2)
        with col1: buy_name = st.text_input("名稱 (如: 晶技)")
        with col2: buy_symbol = st.text_input("代號 (如: 2449)")
        
        buy_price = st.number_input("買入單價*", min_value=0.0, step=0.1)
        buy_qty = st.number_input("買入股數*", min_value=0, step=100, value=1000)
        buy_obs = st.text_area("進場理由")
        
        submitted = st.form_submit_button("✅ 確認買進")
        
        if submitted and (buy_name or buy_symbol) and buy_price > 0 and buy_qty > 0:
            name_val = buy_name.strip() if buy_name.strip() else buy_symbol.strip()
            cost = buy_price * buy_qty
            try:
                new_row = pd.DataFrame([{
                    "日期": datetime.now().strftime("%m/%d"),
                    "標的": name_val, "代號": buy_symbol.strip(),
                    "操作": "買進", "成本": float(buy_price), "股數": int(buy_qty),
                    "投入金額": cost, "漲跌%": 0.0,
                    "盤前觀察": buy_obs.replace('\n', ' '), "盤後紀錄": "實單持倉中"
                }])
                existing_df = conn.read(ttl=0)
                for col in ['代號', '成本', '股數', '投入金額']:
                    if col not in existing_df.columns: existing_df[col] = 0.0 if col != '代號' else ""
                
                conn.update(data=pd.concat([existing_df, new_row], ignore_index=True))
                st.cache_data.clear()
                st.success(f"🎉 {name_val} 已加入實單監控！")
                st.rerun()
            except Exception as e:
                st.error(f"寫入失敗: {str(e)}")

    st.divider()
    
    st.header("📥 盤後筆記批次匯入 (預判)")
    user_input = st.text_area("貼上盤後紀錄與漲跌幅：", height=200)
    if st.button("🚀 開始精密解析"):
        if user_input:
            try:
                new_data = []
                fallback_date = datetime.now().strftime("%m/%d")
                date_blocks = re.split(r'\n(?=\d{1,2}/\d{1,2})', '\n' + user_input.strip())
                for d_block in date_blocks:
                    d_block = d_block.strip()
                    if not d_block: continue
                    lines = d_block.split('\n')
                    date_match = re.match(r'(\d{1,2}/\d{1,2})', lines[0].strip())
                    current_date = date_match.group(1) if date_match else fallback_date
                    content_to_parse = '\n'.join(lines[1:]) if date_match else d_block
                    
                    target_blocks = re.split(r'\n(?=✅|[\u4e00-\u9fa5]{2,5}[:：])', '\n' + content_to_parse)
                    for t_block in target_blocks:
                        t_block = t_block.strip()
                        if not t_block: continue
                        header = t_block.split('\n')[0]
                        if "：" in header or ":" in header:
                            target_raw = re.split(r'[：:]', header)[0].replace('✅', '').strip()
                            target_clean = re.sub(r'\d+', '', target_raw).strip()
                            if len(target_clean) > 8 or not target_clean: continue
                            
                            full_content = "\n".join(t_block.split('\n'))
                            obs_part, rec_part = "", ""
                            if "👉" in full_content:
                                parts = re.split(r'👉[🏻]?', full_content)
                                obs_part = parts[0].split("：", 1)[-1].strip() if "：" in parts[0] else parts[0]
                                rec_part = parts[1].strip()
                            else:
                                obs_part = full_content.split("：", 1)[-1].strip() if "：" in full_content else full_content
                            
                            norm_text = (rec_part if rec_part else full_content).replace('＋', '+').replace('－', '-').replace(' ', '')
                            matches = re.findall(r'([+-]\d+(?:\.\d+)?)', norm_text)
                            change = float(matches[-1]) if matches else 0.0
                            is_buy = "✅" in header or "買" in full_content
                            
                            new_data.append({
                                "日期": current_date, "標的": target_clean, "代號": "",
                                "操作": "買進" if is_buy else "觀察", "成本": 0.0, "股數": 0, "投入金額": 0.0,
                                "漲跌%": change, "盤前觀察": obs_part, "盤後紀錄": rec_part
                            })
                
                if new_data:
                    df_new = pd.DataFrame(new_data)
                    existing_df = conn.read(ttl=0)
                    for col in ['代號', '成本', '股數', '投入金額']:
                        if col not in existing_df.columns: existing_df[col] = 0.0 if col != '代號' else ""
                    conn.update(data=pd.concat([existing_df, df_new], ignore_index=True))
                    st.cache_data.clear()
                    st.success(f"🎊 成功匯入 {len(new_data)} 筆！")
                    st.rerun()
            except Exception as e:
                st.error(f"解析錯誤：{str(e)}")

    st.divider()
    if st.button("🗑️ 一鍵清空舊資料庫"):
        empty_df = pd.DataFrame(columns=["日期", "標的", "代號", "操作", "成本", "股數", "投入金額", "漲跌%", "盤前觀察", "盤後紀錄"])
        conn.update(data=empty_df)
        st.cache_data.clear()
        st.rerun()

# --- 主畫面顯示 ---
try:
    df = conn.read(ttl=0).dropna(subset=['標的'])
    for col in ['代號', '成本', '股數', '投入金額']:
        if col not in df.columns: df[col] = 0.0 if col != '代號' else ""
        
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    df = df[(df['標的'].str.len() <= 6) & (df['標的'].str.len() > 0)]
    df['漲跌%'] = pd.to_numeric(df['漲跌%'], errors='coerce').fillna(0.0)
    df['成本'] = pd.to_numeric(df['成本'], errors='coerce').fillna(0.0)

    if not df.empty:
        # ==========================================
        # 模塊 1：💰 10萬本金與實單持倉監控 (新功能區)
        # ==========================================
        monitor_df = df[(df['操作'] == '買進') & (df['成本'] > 0)].copy()
        
        st.markdown("### 💰 實單持倉與資金雷達 (10萬本金)")
        used_capital = monitor_df['投入金額'].sum() if not monitor_df.empty else 0
        rem_capital = TOTAL_CAPITAL - used_capital
        
        c1, c2, c3 = st.columns(3)
        c1.metric("已投入資金", f"${used_capital:,.0f}")
        c2.metric("剩餘可用資金", f"${rem_capital:,.0f}")
        c3.metric("本金利用率", f"{(used_capital/TOTAL_CAPITAL)*100:.1f}%")

        if not monitor_df.empty:
            plot_data = []
            total_unrealized = 0
            
            # 即時報價卡片
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
                        if profit_pct >= 10:
                            st.error(f"🚨 **{row['標的']}** 已達 10% 停利目標！")
            
            # 第二個圓餅圖：實單持股損益分佈
            if plot_data:
                st.write("")
                st.caption("🔻 實單持股損益貢獻度 (圓餅大小代表影響力，紅色為獲利，綠色為虧損)")
                pdf = pd.DataFrame(plot_data)
                fig_pnl = px.pie(pdf, values='絕對值', names='標的', hole=0.4, color='狀態',
                                 color_discrete_map={'獲利':'#ef5350', '虧損':'#26a69a'})
                fig_pnl.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                st.plotly_chart(fig_pnl, use_container_width=True)

        st.divider()

        # ==========================================
        # 模塊 2：🎯 歷史預判勝率與覆盤日誌 (原版保留區)
        # ==========================================
        st.markdown("### 🎯 歷史預判勝率與覆盤日誌")
        
        # 原版勝率計算與圓餅圖 (依照筆記匯入的 % 數計算)
        buy_df = df[df['操作'] == '買進']
        win_rate = (len(buy_df[buy_df['漲跌%'] > 0]) / len(buy_df) * 100) if len(buy_df) > 0 else 0
        st.metric("📊 實際買進預判勝率", f"{win_rate:.1f}%")
        
        # 完美還原原本的「獲利 vs 虧損」圓餅圖
        df['預判結果'] = df['漲跌%'].apply(lambda x: '獲利' if x > 0 else ('虧損' if x < 0 else '持平'))
        fig_winrate = px.pie(buy_df, names='預判結果', hole=0.4, color='預判結果', 
                             color_discrete_map={'獲利':'#ef5350', '虧損':'#26a69a', '持平':'#bdbdbd'})
        fig_winrate.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
        st.plotly_chart(fig_winrate, use_container_width=True)

        st.write("") # 增加排版間距

        # 完美還原雙頁籤
        tab1, tab2 = st.tabs(["🗂️ 依【個股】深度追蹤", "📅 依【日期】盤後日誌"])

        with tab1:
            for target in sorted(df['標的'].unique()):
                t_df = df[df['標的'] == target].sort_values(by='日期', ascending=False)
                with st.expander(f"📌 {target} (總紀錄：{len(t_df)} 筆)"):
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

        with tab2:
            df['月份'] = df['日期'].apply(lambda x: str(x).split('/')[0] + '月' if '/' in str(x) else '未知')
            def sort_month(m_str):
                try: return int(m_str.replace('月', ''))
                except: return 0
            months = sorted(df['月份'].unique(), key=sort_month, reverse=True)
            for month in months:
                st.markdown(f"#### 🗓️ {month}")
                m_df = df[df['月份'] == month]
                dates = sorted(m_df['日期'].unique(), reverse=True)
                for date in dates:
                    d_df = m_df[m_df['日期'] == date]
                    buy_count = len(d_df[d_df['操作'] == '買進'])
                    obs_count = len(d_df[d_df['操作'] == '觀察'])
                    with st.expander(f"📅 {date} (買進: {buy_count} 檔 | 觀察: {obs_count} 檔)", expanded=True if date == df['日期'].max() else False):
                        for _, row in d_df.iterrows():
                            action_badge = f"<span style='background-color:#ef5350; color:white; padding:2px 6px; border-radius:4px; font-size:0.8rem;'>買進</span>" if row['操作'] == '買進' else f"<span style='background-color:#bdbdbd; color:white; padding:2px 6px; border-radius:4px; font-size:0.8rem;'>觀察</span>"
                            result_color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "gray")
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
