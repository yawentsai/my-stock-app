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

# 1. 標題與設定
st.set_page_config(page_title="零股追蹤神器", layout="wide")
st.title("🚀 零股追蹤神器 7.0 (大整合旗艦版)")

# 2. 每 60 秒自動刷新
st_autorefresh(interval=60000, limit=1000, key="global_refresh")

# 💡 初始本金
INITIAL_CAPITAL = 100000

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 工具：抓取新聞 ---
@st.cache_data(ttl=1800)
def fetch_stock_news(stock_name):
    news_list = []
    try:
        query = urllib.parse.quote(f"{stock_name}")
        url = f"https://news.google.com/rss/search?q={query}+when:3d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        resp = requests.get(url)
        soup = BeautifulSoup(resp.content, features="xml")
        for item in soup.findAll('item')[:8]:
            news_list.append({"標題": item.title.text, "連結": item.link.text, "來源": item.source.text, "發布": item.pubDate.text})
    except: pass
    return news_list

# --- 工具：抓取現價 ---
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

# 強制轉型
for col in ['成本', '股數', '投入金額', '漲跌%', '賣出價', '實現損益']:
    existing_df[col] = pd.to_numeric(existing_df[col], errors='coerce').fillna(0.0)

# --- 側邊欄控制區 ---
with st.sidebar:
    st.header("⚡ 系統控制區")
    with st.expander("🔔 訂閱新聞追蹤", expanded=True):
        with st.form("news_form", clear_on_submit=True):
            n_name = st.text_input("股票名稱")
            n_symbol = st.text_input("代號")
            if st.form_submit_button("📡 開始追蹤") and (n_name or n_symbol):
                val = n_name.strip() if n_name.strip() else n_symbol.strip()
                new_row = pd.DataFrame([{"日期": date.today().strftime("%m/%d"), "標的": val, "代號": n_symbol.strip(), "操作": "追蹤", "盤後紀錄": "僅新聞追蹤"}])
                conn.update(data=pd.concat([existing_df, new_row], ignore_index=True)); st.cache_data.clear(); st.rerun()

    with st.expander("🛒 實單進場登錄"):
        with st.form("buy_form", clear_on_submit=True):
            b_date = st.date_input("日期", value=date.today())
            col1, col2 = st.columns(2)
            with col1: b_name = st.text_input("名稱")
            with col2: b_symbol = st.text_input("代號")
            b_price = st.number_input("均價*", min_value=0.0)
            b_qty = st.number_input("股數*", min_value=1, value=100)
            b_obs = st.text_area("進場理由")
            if st.form_submit_button("✅ 確認買進"):
                val = b_name.strip() if b_name.strip() else b_symbol.strip()
                new_row = pd.DataFrame([{"日期": b_date.strftime("%m/%d"), "標的": val, "代號": b_symbol.strip(), "操作": "買進", "成本": float(b_price), "股數": int(b_qty), "投入金額": b_price*b_qty, "漲跌%": 0.0, "盤前觀察": b_obs, "盤後紀錄": "實單持倉中"}])
                conn.update(data=pd.concat([existing_df, new_row], ignore_index=True)); st.cache_data.clear(); st.rerun()

    with st.expander("💸 賣出結算"):
        active_h = existing_df[(existing_df['操作'] == '買進') & (existing_df['盤後紀錄'] == '實單持倉中')]
        if not active_h.empty:
            with st.form("sell_form", clear_on_submit=True):
                sel = st.selectbox("選擇持倉", active_h.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1))
                s_price = st.number_input("賣出單價", min_value=0.0)
                s_note = st.text_input("出場檢討")
                if st.form_submit_button("💰 確認賣出"):
                    sd, sn = sel.split(" - ", 1)
                    idx = existing_df[(existing_df['日期']==sd) & (existing_df['標的']==sn)].index[0]
                    cp = existing_df.at[idx, '成本']; q = existing_df.at[idx, '股數']
                    existing_df.at[idx, '賣出價'], existing_df.at[idx, '實現損益'] = s_price, (s_price - cp)*q
                    existing_df.at[idx, '漲跌%'], existing_df.at[idx, '盤後紀錄'] = ((s_price - cp)/cp)*100, f"已出場 ({s_note})"
                    conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

# --- 主畫面運算 ---
try:
    df = existing_df.dropna(subset=['標的']).copy()
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    
    total_realized = df['實現損益'].sum()
    active_df = df[(df['操作'] == '買進') & (df['盤後紀錄'] == '實單持倉中')]
    
    total_unrealized = 0; active_holdings_data = []; ready_to_sell = []
    for _, row in active_df.iterrows():
        cp = get_live_price(row['代號'])
        p_pct = ((cp - row['成本']) / row['成本']) * 100 if cp else 0.0
        p_twd = (cp - row['成本']) * row['股數'] if cp else 0.0
        total_unrealized += p_twd
        active_holdings_data.append({'日期': row['日期'], '標的名稱': row['標的'], '代號': row['代號'], '均價': row['成本'], '股數': row['股數'], '投入本金': row['投入金額'], '即時現價': cp if cp else "讀取中...", '損益金額': p_twd, '損益率%': p_pct})
        if p_pct >= 10: ready_to_sell.append(f"{row['標的']} (+{p_pct:.1f}%)")
    
    total_profit = total_realized + total_unrealized
    equity = INITIAL_CAPITAL + total_profit
    used_cap = active_df['投入金額'].sum()
    rem_cap = (INITIAL_CAPITAL + total_realized) - used_cap

    # 1. 2排3欄大字看板
    st.markdown("### 🏦 真實資產結算看板")
    p_c = "#1b5e20" if total_profit >= 0 else "#b71c1c"; p_b = "#e8f5e9" if total_profit >= 0 else "#ffebee"
    st.markdown(f"""<div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-bottom:20px;"><div style="background:#f8f9fa; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#555; margin-bottom:5px;">總資產權益</div><div style="font-size:1.45rem; font-weight:bold;">${equity:,.0f}</div></div><div style="background:{p_b}; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:{p_c}; margin-bottom:5px;">🎯 累計獲利</div><div style="font-size:1.45rem; font-weight:bold; color:{p_c};">${total_profit:,.0f}</div></div><div style="background:#f8f9fa; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#555; margin-bottom:5px;">📈 ROI</div><div style="font-size:1.45rem; font-weight:bold;">{(total_profit/INITIAL_CAPITAL)*100:.2f}%</div></div><div style="background:#fff3e0; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#e65100; margin-bottom:5px;">已投入資金</div><div style="font-size:1.45rem; font-weight:bold; color:#e65100;">${used_cap:,.0f}</div></div><div style="background:#f8f9fa; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#555; margin-bottom:5px;">可用現金</div><div style="font-size:1.45rem; font-weight:bold;">${rem_cap:,.0f}</div></div><div style="background:#f8f9fa; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#555; margin-bottom:5px;">利用率</div><div style="font-size:1.45rem; font-weight:bold;">{(used_cap/(INITIAL_CAPITAL+total_realized))*100:.1f}%</div></div></div>""", unsafe_allow_html=True)

    # 2. 停利提示框
    if ready_to_sell:
        st.markdown(f"<div style='padding:15px; border-radius:8px; background-color:#ffebee; border:2px solid #ef5350; margin-bottom:20px;'><h4 style='margin-top:0; color:#c62828;'>🚨 停利標準已達標 ({len(ready_to_sell)} 檔)</h4><p style='margin-bottom:0; font-size:1.1rem; color:#b71c1c; font-weight:bold;'>👉 可賣出：{', '.join(ready_to_sell)}</p></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='padding:10px; border-radius:8px; background-color:#f1f3f4; border:1px dashed #999; margin-bottom:20px; text-align:center;'><span style='color:#666; font-size:0.9rem;'>✅ 目前持股獲利尚未達 10% 停利標準，請繼續耐心持有。</span></div>", unsafe_allow_html=True)

    # 3. 頁籤功能
    t1, t2, t3, t4 = st.tabs(["💼 實單持股", "📰 即時新聞區", "📅 歷史日誌", "🗂️ 個股追蹤"])
    
    with t1:
        if active_holdings_data:
            st.dataframe(pd.DataFrame(active_holdings_data), use_container_width=True, hide_index=True, column_config={"日期": st.column_config.TextColumn(width=60), "損益金額": st.column_config.NumberColumn(format="$%d"), "損益率%": st.column_config.NumberColumn(format="%.2f%%")})
        else: st.info("目前無持倉紀錄。")

    with t2:
        news_watchlist = sorted(list(set(list(active_df['標的'].unique()) + list(df[df['操作'] == '追蹤']['標的'].unique()))))
        if news_watchlist:
            for s in news_watchlist:
                with st.expander(f"📢 {s} - 情報監控", expanded=True):
                    for n in fetch_stock_news(s):
                        st.markdown(f"<div style='padding:8px; border-bottom:1px solid #eee;'><a href='{n['連結']}' target='_blank' style='text-decoration:none; color:#1e88e5; font-weight:bold;'>{n['標題']}</a><br><small style='color:gray;'>{n['來源']} | {n['發布']}</small></div>", unsafe_allow_html=True)
        else: st.info("請在側邊欄訂閱標的以開始監控新聞。")

    completed_df = df[~df['盤後紀錄'].isin(["實單持倉中", "⏳ 等待更新...", "僅新聞追蹤"])].copy()
    with t3:
        if not completed_df.empty:
            for d in sorted(completed_df['日期'].unique(), reverse=True):
                with st.expander(f"📅 {d}", expanded=True if d == completed_df['日期'].max() else False):
                    for _, r in completed_df[completed_df['日期']==d].iterrows():
                        bg = "#ef5350" if r['操作'] == '買進' else "#bdbdbd"; res_c = "#ef5350" if r['漲跌%'] > 0 else ("#26a69a" if r['漲跌%'] < 0 else "gray")
                        st.markdown(f"<div style='padding:8px; border-bottom:1px solid #eee;'><span style='background-color:{bg}; color:white; padding:2px 6px; border-radius:4px; font-size:0.8rem;'>{r['操作']}</span> <strong>{r['標的']}</strong> <span style='color:{res_c}; float:right; font-weight:bold;'>{r['漲跌%']:.1f}%</span><br><span style='color:#666; font-size:0.85rem; display:block; margin-top:4px;'>📝 {r['盤後紀錄']}</span></div>", unsafe_allow_html=True)

    with t4:
        if not completed_df.empty:
            for t in sorted(completed_df['標的'].unique()):
                t_df = completed_df[completed_df['標的'] == t].sort_values(by='日期', ascending=False)
                with st.expander(f"📌 {t} (紀錄：{len(t_df)} 筆)"):
                    for _, row in t_df.iterrows():
                        color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "#bdbdbd")
                        st.markdown(f"<div style='border-left:5px solid {color}; padding:10px; background:#f8f9fa; margin-bottom:10px; border-radius:4px;'><b>{row['日期']} | {row['操作']} | <span style='color:{color};'>{row['漲跌%']:.1f}%</span></b><br><div style='margin-top:6px; font-size:0.92rem; line-height:1.5;'><span style='color:#555;'>🔍 <b>盤前：</b> {row['盤前觀察']}</span><br><span style='color:#222;'>📝 <b>盤後：</b> {row['盤後紀錄']}</span></div></div>", unsafe_allow_html=True)

    # 4. 底部績效看板
    st.divider()
    st.markdown("### 🎯 歷史預判與覆盤日誌")
    c_buy = completed_df[completed_df['操作'] == '買進']
    w_r = (len(c_buy[c_buy['實現損益'] > 0]) / len(c_buy) * 100) if not c_buy.empty else 0.0
    st.markdown(f"<div style='margin-bottom:10px;'><span style='font-size:1.1rem; color:#555;'>📊 實際買進預判勝率</span><br><span style='font-size:2.5rem; font-weight:bold; color:#2196f3;'>{w_r:.1f}%</span></div>", unsafe_allow_html=True)
    if not df.empty:
        fig = px.pie(df, names='操作', hole=0.4, color='操作', color_discrete_map={'買進':'#2196f3', '觀察':'#bdbdbd', '追蹤':'#ffeb3b'})
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300); st.plotly_chart(fig, use_container_width=True)

except Exception as e: st.info(f"載入中... ({e})")
