import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import requests
from bs4 import BeautifulSoup
import urllib.parse

# 1. 基礎設定與手機版網格鎖定
st.set_page_config(page_title="零股追蹤神器", layout="wide")
st.title("🚀 零股追蹤神器")

# 樣式定義 (保留原始樣式並優化)
st.markdown("""
    <style>
    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr) !important;
        gap: 8px !important;
        margin-bottom: 20px;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 12px 5px !important;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #ddd;
    }
    .metric-label { font-size: 0.8rem; color: #555; margin-bottom: 4px; }
    .metric-value { font-size: 1.15rem; font-weight: bold; }
    
    section[data-testid="stSidebar"] .stExpander {
        border: 1px solid #eee !important;
        border-radius: 8px !important;
        margin-bottom: 12px !important;
    }
    .status-box {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 20px;
        text-align: center;
        font-size: 0.95rem;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

# --- LINE 通知核心函數 ---
def send_line_message(message):
    try:
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
    except:
        return False

# 2. 自動刷新 (60秒)
st_autorefresh(interval=60000, limit=1000, key="global_v86_final")

INITIAL_CAPITAL = 100000
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 工具函數 ---
@st.cache_data(ttl=1800)
def fetch_stock_news(stock_name):
    news_list = []
    try:
        query = urllib.parse.quote(f"{stock_name}")
        url = f"https://news.google.com/rss/search?q={query}+when:3d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        resp = requests.get(url, timeout=5)
        soup = BeautifulSoup(resp.content, features="xml")
        for item in soup.findAll('item')[:8]:
            news_list.append({"標題": item.title.text, "連結": item.link.text, "來源": item.source.text, "發布": item.pubDate.text})
    except: pass
    return news_list

@st.cache_data(ttl=60)
def get_live_price(symbol):
    if not symbol or symbol == "": return None
    try:
        ticker = f"{symbol}.TW"
        return yf.Ticker(ticker).fast_info['last_price']
    except:
        try:
            ticker = f"{symbol}.TWO"
            return yf.Ticker(ticker).fast_info['last_price']
        except: return None

# --- 讀取資料庫 ---
try:
    existing_df = conn.read(ttl=0)
except:
    existing_df = pd.DataFrame(columns=['日期', '標的', '代號', '操作', '成本', '股數', '投入金額', '漲跌%', '盤前觀察', '盤後紀錄', '賣出價', '實現損益'])

for col in ['成本', '股數', '投入金額', '賣出價', '實現損益', '漲跌%']:
    existing_df[col] = pd.to_numeric(existing_df[col], errors='coerce').fillna(0.0)

# --- 側邊欄：功能全開 ---
with st.sidebar:
    st.header("⚡ 系統控制區")
    
    # LINE 通知測試按鈕
    st.subheader("🔔 通知測試")
    if st.button("發送 LINE 測試通知"):
        if send_line_message("✅ 零股追蹤神器：連線測試成功！"):
            st.success("通知已發送，請檢查手機！")
        else:
            st.error("發送失敗，請檢查 Secrets 設定。")
    st.divider()

    with st.expander("🌅 Step 1: 盤前計畫"):
        with st.form("pre_m", clear_on_submit=True):
            p_date = st.text_input("日期", value=date.today().strftime("%m/%d"))
            p_action = st.selectbox("性質", ["觀察", "✅ 買進"])
            p_name = st.text_input("股票名稱*")
            p_symbol = st.text_input("代號")
            p_pre = st.text_area("🔍 盤前觀點")
            if st.form_submit_button("🚀 發布"):
                new_r = pd.DataFrame([{"日期": p_date, "標的": p_name.strip(), "代號": p_symbol.strip(), "操作": "買進" if "買進" in p_action else "觀察", "成本": 0.0, "股數": 0, "投入金額": 0.0, "漲跌%": 0.0, "盤前觀察": p_pre, "盤後紀錄": "⏳ 等待更新...", "賣出價": 0.0, "實現損益": 0.0}])
                conn.update(data=pd.concat([existing_df, new_r], ignore_index=True)); st.cache_data.clear(); st.rerun()

    with st.expander("🌇 Step 2: 盤後統整"):
        waiting = existing_df[existing_df['盤後紀錄'] == "⏳ 等待更新..."]
        if not waiting.empty:
            with st.form("post_m", clear_on_submit=True):
                target = st.selectbox("選取標的", waiting.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1))
                res_pct = st.number_input("漲跌 %", step=0.01, format="%.2f")
                res_post = st.text_area("📝 盤後回饋")
                if st.form_submit_button("💾 儲存"):
                    sd, sn = target.split(" - ", 1)
                    idx = existing_df[(existing_df['日期']==sd) & (existing_df['標的']==sn)].index[0]
                    existing_df.at[idx, '漲跌%'], existing_df.at[idx, '盤後紀錄'] = float(res_pct), res_post
                    conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

    st.divider()

    with st.expander("🛒 實單庫存：買入登錄"):
        with st.form("buy_f"):
            br_date = st.date_input("日期", value=date.today())
            br_n, br_s = st.text_input("名稱"), st.text_input("代號")
            br_p = st.number_input("均價", min_value=0.0); br_q = st.number_input("股數", min_value=1, value=100)
            if st.form_submit_button("✅ 加入持倉"):
                new_r = pd.DataFrame([{"日期": br_date.strftime("%m/%d"), "標的": br_n, "代號": br_s, "操作": "買進", "成本": float(br_p), "股數": int(br_q), "投入金額": br_p*br_q, "漲跌%": 0.0, "盤後紀錄": "實單持倉中"}])
                conn.update(data=pd.concat([existing_df, new_r], ignore_index=True)); st.cache_data.clear(); st.rerun()

    with st.expander("💸 實單庫存：賣出結算"):
        active_h = existing_df[existing_df['盤後紀錄'] == "實單持倉中"]
        if not active_h.empty:
            with st.form("sell_f"):
                sel = st.selectbox("選取結算對象", active_h.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1))
                sr_p = st.number_input("賣出單價", min_value=0.0)
                sd_sel, sn_sel = sel.split(" - ", 1)
                curr_row = existing_df[(existing_df['日期']==sd_sel) & (existing_df['標的']==sn_sel)].iloc[0]
                sr_q = st.number_input(f"賣出股數 (持有: {int(curr_row['股數'])})", min_value=1, max_value=int(curr_row['股數']), value=int(curr_row['股數']))
                sr_n = st.text_input("出場筆記")
                if st.form_submit_button("💰 結算獲利"):
                    idx = existing_df[(existing_df['日期']==sd_sel) & (existing_df['標的']==sn_sel)].index[0]
                    cp, q_orig = existing_df.at[idx, '成本'], existing_df.at[idx, '股數']
                    if sr_q < q_orig:
                        new_sold = existing_df.loc[[idx]].copy()
                        new_sold['股數'], new_sold['投入金額'], new_sold['賣出價'] = sr_q, cp * sr_q, sr_p
                        new_sold['實現損益'], new_sold['漲跌%'], new_sold['盤後紀錄'] = (sr_p - cp) * sr_q, ((sr_p - cp)/cp)*100, f"減碼：{sr_n}"
                        existing_df.at[idx, '股數'] = q_orig - sr_q
                        existing_df.at[idx, '投入金額'] = cp * (q_orig - sr_q)
                        existing_df = pd.concat([existing_df, new_sold], ignore_index=True)
                    else:
                        existing_df.at[idx, '賣出價'], existing_df.at[idx, '實現損益'] = sr_p, (sr_p - cp) * q_orig
                        existing_df.at[idx, '漲跌%'], existing_df.at[idx, '盤後紀錄'] = ((sr_p - cp)/cp)*100, f"清倉：{sr_n}"
                    conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

# --- 主畫面顯示 ---
try:
    df = existing_df.dropna(subset=['標的']).copy()
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    
    total_realized = df['實現損益'].sum()
    active_df = df[df['盤後紀錄'] == '實單持倉中']
    
    total_unrealized = 0; active_holdings = []; ready_to_sell = []
    for _, row in active_df.iterrows():
        cp = get_live_price(row['代號'])
        p_pct = ((cp - row['成本']) / row['成本']) * 100 if cp else 0.0
        p_twd = (cp - row['成本']) * row['股數'] if cp else 0.0
        total_unrealized += p_twd
        active_holdings.append({'日期': row['日期'], '標的': row['標的'], '代號': row['代號'], '均價': row['成本'], '股數': row['股數'], '現價': cp if cp else "...", '損益金額': p_twd, '損益率%': p_pct})
        # 💡 通知邏輯：獲利達 2.00%
        if p_pct >= 2.0: ready_to_sell.append(f"{row['標的']} (+{p_pct:.2f}%)")
    
    total_profit = total_realized + total_unrealized
    equity = INITIAL_CAPITAL + total_profit; used_cap = active_df['投入金額'].sum(); rem_cap = (INITIAL_CAPITAL + total_realized) - used_cap

    # 1. 看板
    st.markdown("### 🏦 真實資產結算看板")
    p_c = "#1b5e20" if total_profit >= 0 else "#b71c1c"; p_b = "#e8f5e9" if total_profit >= 0 else "#ffebee"
    st.markdown(f"""<div class="dashboard-grid"><div class="metric-card"><div class="metric-label">總資產權益</div><div class="metric-value">${equity:,.0f}</div></div><div class="metric-card" style="background:{p_b}; border-color:{p_c}22;"><div class="metric-label" style="color:{p_c};">🎯 累計獲利</div><div class="metric-value" style="color:{p_c};">${total_profit:,.0f}</div></div><div class="metric-card"><div class="metric-label">📈 ROI</div><div class="metric-value">{(total_profit/INITIAL_CAPITAL)*100:.2f}%</div></div><div class="metric-card" style="background:#fff3e0;"><div class="metric-label" style="color:#e65100;">已投入資金</div><div class="metric-value" style="color:#e65100;">${used_cap:,.0f}</div></div><div class="metric-card"><div class="metric-label">可用現金</div><div class="metric-value">${rem_cap:,.0f}</div></div><div class="metric-card"><div class="metric-label">利用率</div><div class="metric-value">{(used_cap/(INITIAL_CAPITAL+total_realized))*100:.1f}%</div></div></div>""", unsafe_allow_html=True)

    # 🚦 獲利狀態通知
    if ready_to_sell:
        status_msg = f"🚨 停利標準已達標 (2%↑)：{', '.join(ready_to_sell)}"
        st.markdown(f"""<div class="status-box" style="background-color:#ffebee; color:#b71c1c; border:2px solid #ef5350;">{status_msg}</div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="status-box" style="background-color:#e8f5e9; color:#2e7d32; border:1px dashed #4caf50;">✅ 目前持股獲利尚未達 2% 停利標準，請繼續耐心持有。</div>""", unsafe_allow_html=True)

    t1, t2, t3, t4 = st.tabs(["💼 實單持股", "📰 即時新聞區", "📅 歷史日誌 (統整)", "🗂️ 個股深度追蹤"])
    
    with t1:
        if active_holdings:
            st.dataframe(pd.DataFrame(active_holdings), use_container_width=True, hide_index=True, column_config={"損益率%": st.column_config.NumberColumn(format="%.2f%%")})
        else: st.info("目前無持倉。")

    with t2:
        news_w = sorted(list(set(list(active_df['標的'].unique()) + list(df[df['操作'] == '追蹤']['標的'].unique()))))
        for s in news_w:
            with st.expander(f"📢 {s} - 情報監控", expanded=True):
                for n in fetch_stock_news(s):
                    st.markdown(f"<div style='padding:8px; border-bottom:1px solid #eee;'><a href='{n['連結']}' target='_blank' style='text-decoration:none; color:#1e88e5; font-weight:bold;'>{n['標題']}</a><br><small style='color:gray;'>{n['來源']} | {n['發布']}</small></div>", unsafe_allow_html=True)

    completed = df[~df['盤後紀錄'].isin(["實單持倉中", "⏳ 等待更新...", "僅新聞追蹤"])].copy()
    
    with t3:
        if not completed.empty:
            for d in sorted(completed['日期'].unique(), reverse=True):
                with st.expander(f"🗓️ {d} 操盤戰報", expanded=(d == completed['日期'].max())):
                    for _, r in completed[completed['日期'] == d].iterrows():
                        res_c = "#ef5350" if r['漲跌%'] > 0 else ("#26a69a" if r['漲跌%'] < 0 else "gray")
                        bg = "#ef5350" if "買進" in r['操作'] else "#bdbdbd"
                        st.markdown(f"""<div style="border-left:6px solid {res_c}; padding:15px; background:white; margin-bottom:12px; border-radius:8px; border: 1px solid #eee;"><div style="display:flex; justify-content:space-between; margin-bottom:8px;"><span style='background-color:{bg}; color:white; padding:2px 8px; border-radius:4px; font-size:0.8rem;'>{r['操作']}</span><strong>{r['標的']}</strong><span style="color:{res_c}; font-weight:bold;">{r['漲跌%']:.2f}%</span></div><div style="background:#f8f9fa; padding:8px; border-radius:6px; margin-bottom:5px; font-size:0.9rem;">🔍 盤前：{r['盤前觀察']}</div><div style="background:#fff; padding:8px; border-radius:6px; border:1px dashed #ddd; font-size:0.9rem;">📝 盤後：{r['盤後紀錄']}</div></div>""", unsafe_allow_html=True)

    with t4:
        if not completed.empty:
            for t in sorted(completed['標的'].unique()):
                t_df = completed[completed['標的'] == t].sort_values(by='日期', ascending=False)
                with st.expander(f"📌 {t} (紀錄：{len(t_df)} 筆)"):
                    for _, row in t_df.iterrows():
                        c = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "#bdbdbd")
                        st.markdown(f"<div style='border-left:5px solid {c}; padding:10px; background:#f8f9fa; margin-bottom:10px; border-radius:4px;'><b>{row['日期']} | <span style='color:{c};'>{row['漲跌%']:.2f}%</span></b><br><small>🔍 {row['盤前觀察']}</small><br><small>📝 {row['盤後紀錄']}</small></div>", unsafe_allow_html=True)

    # 4. 底部圖表
    st.divider()
    c_buy = completed[completed['操作'] == '買進']
    w_r = (len(c_buy[c_buy['漲跌%'] > 0]) / len(c_buy) * 100) if not c_buy.empty else 0.0
    st.markdown(f"<div><span style='font-size:1.1rem; color:#555;'>📊 實際預判勝率</span><br><span style='font-size:2.5rem; font-weight:bold; color:#2196f3;'>{w_r:.1f}%</span></div>", unsafe_allow_html=True)
    if not df.empty:
        fig = px.pie(df, names='操作', hole=0.4, color='操作', color_discrete_map={'買進':'#2196f3', '觀察':'#bdbdbd', '追蹤':'#ffeb3b'})
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300); st.plotly_chart(fig, use_container_width=True)

except Exception as e: st.info(f"系統準備中... ({e})")
