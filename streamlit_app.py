import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re
from datetime import datetime
import yfinance as yf

st.set_page_config(page_title="交易戰情室 3.7", layout="wide")
st.title("🛰️ 交易戰情室 3.7 (即時監控與快登版)")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 工具函數：抓取台股現價 ---
@st.cache_data(ttl=300) # 每 5 分鐘快取一次，避免 API 呼叫過度
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
        st.caption("盤中達標時，直接在此輸入買進紀錄")
        col1, col2 = st.columns(2)
        with col1:
            buy_name = st.text_input("標的名稱 (如: 晶技)*")
        with col2:
            buy_symbol = st.text_input("股票代號 (如: 2449)*")
        
        buy_price = st.number_input("買入價格 (成本)*", min_value=0.0, step=0.5, format="%.2f")
        buy_obs = st.text_area("盤前預判與買進理由")
        
        submitted = st.form_submit_button("✅ 確認買進並加入監控")
        
        if submitted:
            if buy_name and buy_symbol and buy_price > 0:
                try:
                    new_row = pd.DataFrame([{
                        "日期": datetime.now().strftime("%m/%d"),
                        "標的": buy_name.strip(),
                        "代號": buy_symbol.strip(),
                        "操作": "買進",
                        "成本": float(buy_price),
                        "漲跌%": 0.0,
                        "盤前觀察": buy_obs.replace('\n', ' '),
                        "盤後紀錄": "監控中..."
                    }])
                    existing_df = conn.read(ttl=0)
                    # 確保舊資料表有新欄位
                    if '代號' not in existing_df.columns: existing_df['代號'] = ""
                    if '成本' not in existing_df.columns: existing_df['成本'] = 0.0
                    
                    updated_df = pd.concat([existing_df, new_row], ignore_index=True)
                    conn.update(data=updated_df)
                    st.cache_data.clear()
                    st.success(f"🎉 {buy_name} 已成功加入即時監控！")
                    st.rerun()
                except Exception as e:
                    st.error(f"寫入失敗: {str(e)}")
            else:
                st.warning("請填寫完整的名稱、代號與價格！")

    st.divider()
    
    st.header("📥 盤後筆記批次匯入")
    user_input = st.text_area("在此貼上觀察筆記：", height=200)
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
                        t_lines = t_block.split('\n')
                        header = t_lines[0]
                        
                        if "：" in header or ":" in header:
                            target_raw = re.split(r'[：:]', header)[0].replace('✅', '').strip()
                            target_clean = re.sub(r'\d+', '', target_raw).strip()
                            if len(target_clean) > 8 or not target_clean: continue
                            
                            full_content = "\n".join(t_lines)
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
                                "操作": "買進" if is_buy else "觀察", "成本": 0.0,
                                "漲跌%": change, "盤前觀察": obs_part, "盤後紀錄": rec_part
                            })
                
                if new_data:
                    df_new = pd.DataFrame(new_data)
                    existing_df = conn.read(ttl=0)
                    if '代號' not in existing_df.columns: existing_df['代號'] = ""
                    if '成本' not in existing_df.columns: existing_df['成本'] = 0.0
                    updated_df = pd.concat([existing_df, df_new], ignore_index=True)
                    conn.update(data=updated_df)
                    st.cache_data.clear()
                    st.success(f"🎊 成功匯入 {len(new_data)} 筆！")
                    st.rerun()
            except Exception as e:
                st.error(f"解析錯誤：{str(e)}")

    st.divider()
    st.header("⚙️ 系統管理")
    if st.button("🗑️ 一鍵清空舊資料庫"):
        empty_df = pd.DataFrame(columns=["日期", "標的", "代號", "操作", "成本", "漲跌%", "盤前觀察", "盤後紀錄"])
        conn.update(data=empty_df)
        st.cache_data.clear()
        st.success("✅ 資料庫已徹底清空！")
        st.rerun()

# --- 主畫面顯示 ---
try:
    df = conn.read(ttl=0).dropna(subset=['標的'])
    if '代號' not in df.columns: df['代號'] = ""
    if '成本' not in df.columns: df['成本'] = 0.0
    
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    df = df[(df['標的'].str.len() <= 6) & (df['標的'].str.len() > 0)]
    df['漲跌%'] = pd.to_numeric(df['漲跌%'], errors='coerce').fillna(0.0)
    df['成本'] = pd.to_numeric(df['成本'], errors='coerce').fillna(0.0)
    
    if not df.empty:
        # --- 🏆 10% 獲利即時監控面板 ---
        monitor_df = df[(df['操作'] == '買進') & (df['代號'].astype(str).str.strip() != "") & (df['成本'] > 0)].drop_duplicates(subset=['標的'], keep='last')
        
        if not monitor_df.empty:
            st.subheader("📡 即時持倉雷達 (自動試算損益)")
            cols = st.columns(3)
            
            for i, (idx, row) in enumerate(monitor_df.iterrows()):
                current_price = get_live_price(row['代號'])
                
                if current_price:
                    profit_pct = ((current_price - row['成本']) / row['成本']) * 100
                    with cols[i % 3]:
                        st.markdown(f"""
                        <div style="padding:15px; background:white; border-radius:10px; border: 1px solid #ddd; border-left: 5px solid {'#ef5350' if profit_pct>=10 else '#2196f3'};">
                            <h4 style="margin:0;">{row['標的']} ({row['代號']})</h4>
                            <p style="margin:5px 0; color:gray; font-size:14px;">成本: ${row['成本']} | 現價: ${current_price:.2f}</p>
                            <h3 style="margin:0; color:{'#ef5350' if profit_pct>0 else '#26a69a'};">{'+' if profit_pct>0 else ''}{profit_pct:.2f}%</h3>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if profit_pct >= 10:
                            st.error(f"🚨 **{row['標的']}** 已達 10% 停利目標！請評估出場。")
                else:
                    with cols[i % 3]:
                        st.info(f"{row['標的']} ({row['代號']}) 讀取報價中...")
            st.divider()

        # --- 歷史勝率與圖表 ---
        buy_df = df[df['操作'] == '買進']
        win_rate = (len(buy_df[buy_df['漲跌%'] > 0]) / len(buy_df) * 100) if len(buy_df) > 0 else 0
        st.metric("📊 實際買進預判勝率", f"{win_rate:.1f}%")
        
        fig = px.pie(df, names='操作', hole=0.4, color='操作', 
                     color_discrete_map={'買進':'#ef5350', '觀察':'#bdbdbd'})
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        tab1, tab2 = st.tabs(["🗂️ 依【個股】深度追蹤", "📅 依【日期】盤後日誌"])

        with tab1:
            st.subheader("🔍 個股深度追蹤歷程")
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
            st.subheader("📝 每日操作與資金流向總覽")
            df['月份'] = df['日期'].apply(lambda x: str(x).split('/')[0] + '月' if '/' in str(x) else '未知')
            def sort_month(m_str):
                try: return int(m_str.replace('月', ''))
                except: return 0
            months = sorted(df['月份'].unique(), key=sort_month, reverse=True)
            for month in months:
                st.markdown(f"### 🗓️ {month}")
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
        st.info("資料庫目前為空，請在左側輸入資料。")
except Exception as e:
    st.info(f"系統啟動中... ({str(e)})")
