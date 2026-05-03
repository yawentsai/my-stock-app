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
st.title("🚀 零股追蹤神器")

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
        resp = requests.get(url, timeout=5)
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
for col in ['成本', '股數', '投入金額', '賣出價', '實現損益', '漲跌%']:
    existing_df[col] = pd.to_numeric(existing_df[col], errors='coerce').fillna(0.0)

# --- 側邊欄：流程控制 ---
with st.sidebar:
    st.header("⚡ 系統控制區")
    
    with st.expander("🌅 Step 1: 盤前計畫輸入", expanded=True):
        with st.form("pre_market", clear_on_submit=True):
            p_date = st.text_input("計畫日期", value=date.today().strftime("%m/%d"))
            p_action = st.selectbox("動作性質", ["觀察", "✅ 買進"])
            p_name = st.text_input("股票名稱*")
            p_symbol = st.text_input("代號")
            p_pre = st.text_area("🔍 盤前核心計畫")
            if st.form_submit_button("🚀 發布計畫") and p_name:
                new_row = pd.DataFrame([{"日期": p_date, "標的": p_name.strip(), "代號": p_symbol.strip(), "操作": "買進" if "買進" in p_action else "觀察", "成本": 0.0, "股數": 0, "投入金額": 0.0, "漲跌%": 0.0, "盤前觀察": p_pre, "盤後紀錄": "⏳ 等待收盤回饋...", "賣出價": 0.0, "實現損益": 0.0}])
                conn.update(data=pd.concat([existing_df, new_row], ignore_index=True)); st.cache_data.clear(); st.rerun()

    with st.expander("🌇 Step 2: 盤後結果統整"):
        waiting = existing_df[existing_df['盤後紀錄'] == "⏳ 等待收盤回饋..."]
        if not waiting.empty:
            with st.form("post_market", clear_on_submit=True):
                target = st.selectbox("選取標的", waiting.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1))
                res_pct = st.number_input("結果漲跌 %", step=0.1)
                res_post = st.text_area("📝 盤後回饋")
                if st.form_submit_button("💾 統整完成"):
                    sd, sn = target.split(" - ", 1)
                    idx = existing_df[(existing_df['日期']==sd) & (existing_df['標的']==sn)].index[0]
                    existing_df.at[idx, '漲跌%'], existing_df.at[idx, '盤後紀錄'] = float(res_pct), res_post
                    conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

    st.divider()
    with st.expander("🛒 實單進場 (庫存)"):
        with st.form("buy_real"):
            br_date = st.date_input("買進日期", value=date.today())
            br_name, br_symbol = st.text_input("股票名稱"), st.text_input("代號")
            br_price = st.number_input("均價", min_value=0.0); br_qty = st.number_input("股數", min_value=1, value=100)
            if st.form_submit_button("✅ 加入持倉"):
                new_r = pd.DataFrame([{"日期": br_date.strftime("%m/%d"), "標的": br_name, "代號": br_symbol, "操作": "買進", "成本": float(br_price), "股數": int(br_qty), "投入金額": br_price*br_qty, "漲跌%": 0.0, "盤後紀錄": "實單持倉中"}])
                conn.update(data=pd.concat([existing_df, new_r], ignore_index=True)); st.cache_data.clear(); st.rerun()

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
        active_holdings_data.append({'日期': row['日期'], '標的名稱': row['標的'], '代號': row['代號'], '均價': row['成本'], '股數': row['股數'], '投入本金': row['投入金額'], '現價': cp if cp else "讀取中...", '損益金額': p_twd, '損益率%': p_pct})
        if p_pct >= 10: ready_to_sell.append(f"{row['標的']} (+{p_pct:.1f}%)")
    
    total_profit = total_realized + total_unrealized
    equity = INITIAL_CAPITAL + total_profit; used_cap = active_df['投入金額'].sum(); rem_cap = (INITIAL_CAPITAL + total_realized) - used_cap

    # 1. 核心看板
    st.markdown("### 🏦 真實資產結算看板")
    p_c = "#1b5e20" if total_profit >= 0 else "#b71c1c"; p_b = "#e8f5e9" if total_profit >= 0 else "#ffebee"
    st.markdown(f"""<div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-bottom:20px;"><div style="background:#f8f9fa; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#555;">總資產權益</div><div style="font-size:1.45rem; font-weight:bold;">${equity:,.0f}</div></div><div style="background:{p_b}; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:{p_c};">🎯 累計獲利</div><div style="font-size:1.45rem; font-weight:bold; color:{p_c};">${total_profit:,.0f}</div></div><div style="background:#f8f9fa; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#555;">📈 ROI</div><div style="font-size:1.45rem; font-weight:bold;">{(total_profit/INITIAL_CAPITAL)*100:.2f}%</div></div><div style="background:#fff3e0; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#e65100;">已投入資金</div><div style="font-size:1.45rem; font-weight:bold; color:#e65100;">${used_cap:,.0f}</div></div><div style="background:#f8f9fa; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#555;">可用現金</div><div style="font-size:1.45rem; font-weight:bold;">${rem_cap:,.0f}</div></div><div style="background:#f8f9fa; padding:15px 10px; border-radius:8px; text-align:center; border:1px solid #ddd;"><div style="font-size:1.05rem; color:#555;">利用率</div><div style="font-size:1.45rem; font-weight:bold;">{(used_cap/(INITIAL_CAPITAL+total_realized))*100:.1f}%</div></div></div>""", unsafe_allow_html=True)

    # 2. 停利提示
    if ready_to_sell:
        st.markdown(f"<div style='padding:15px; border-radius:8px; background-color:#ffebee; border:2px solid #ef5350; margin-bottom:20px;'><h4 style='margin-top:0; color:#c62828;'>🚨 停利標準已達標 ({len(ready_to_sell)} 檔)</h4><p style='margin-bottom:0; font-size:1.1rem; color:#b71c1c; font-weight:bold;'>👉 可賣出：{', '.join(ready_to_sell)}</p></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='padding:10px; border-radius:8px; background-color:#f1f3f4; border:1px dashed #999; margin-bottom:20px; text-align:center;'><span style='color:#666; font-size:0.9rem;'>✅ 目前持股獲利尚未達 10% 停利標準，請繼續耐心持有。</span></div>", unsafe_allow_html=True)

    # 3. 頁籤與回歸樣式
    t1, t2, t3, t4 = st.tabs(["💼 實單持股", "📰 即時新聞區", "📅 歷史日誌 (統整)", "🗂️ 個股深度追蹤"])
    
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

    completed = df[~df['盤後紀錄'].isin(["實單持倉中", "⏳ 等待收盤回饋...", "僅新聞追蹤"])].copy()
    
    with t3: # 💡 歷史日誌：[更新] 改成可收合樣式
        if not completed.empty:
            for d in sorted(completed['日期'].unique(), reverse=True):
                st.markdown(f"#### 📅 {d}")
                day_df = completed[completed['日期'] == d]
                for _, r in day_df.iterrows():
                    res_c = "#ef5350" if r['漲跌%'] > 0 else ("#26a69a" if r['漲跌%'] < 0 else "gray")
                    icon = "🚩" if "買進" in r['操作'] else "🔍"
                    # 將每一檔標的放入摺疊區，標題包含結果
                    with st.expander(f"{icon} {r['標的']} | {r['漲跌%']:.1f}%", expanded=False):
                        bg = "#ef5350" if r['操作'] == '買進' else "#bdbdbd"
                        st.markdown(f"""
                        <div style="border-left:6px solid {res_c}; padding:15px; background:white; border-radius:8px; border: 1px solid #eee;">
                            <div style="background:#f8f9fa; padding:8px; border-radius:6px; margin-bottom:5px;">
                                <span style="color:#666; font-size:0.85rem;">🔍 盤前：</span>{r['盤前觀察']}
                            </div>
                            <div style="background:#fff; padding:8px; border-radius:6px; border:1px dashed #ddd;">
                                <span style="color:#666; font-size:0.85rem;">📝 盤後：</span>{r['盤後紀錄']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
        else: st.info("尚無統整紀錄。")

    with t4: # 💡 個股深度追蹤
        if not completed.empty:
            for t in sorted(completed['標的'].unique()):
                t_df = completed[completed['標的'] == t].sort_values(by='日期', ascending=False)
                with st.expander(f"📌 {t} (紀錄：{len(t_df)} 筆)"):
                    for _, row in t_df.iterrows():
                        color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "#bdbdbd")
                        st.markdown(f"""
                        <div style="border-left:5px solid {color}; padding:10px; background:#f8f9fa; margin-bottom:10px; border-radius:4px;">
                            <b>{row['日期']} | {row['操作']} | <span style="color:{color};">{row['漲跌%']:.1f}%</span></b><br>
                            <div style="margin-top:6px; font-size:0.92rem; line-height:1.5;">
                                <span style="color:#555;">🔍 <b>盤前：</b> {row['盤前觀察']}</span><br>
                                <span style="color:#222;">📝 <b>盤後：</b> {row['盤後紀錄']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    st.divider()
    c_buy = completed[completed['操作'] == '買進']
    w_r = (len(c_buy[c_buy['漲跌%'] > 0]) / len(c_buy) * 100) if not c_buy.empty else 0.0
    st.markdown(f"<div><span style='font-size:1.1rem; color:#555;'>📊 實際買進預判勝率</span><br><span style='font-size:2.5rem; font-weight:bold; color:#2196f3;'>{w_r:.1f}%</span></div>", unsafe_allow_html=True)
    if not df.empty:
        fig = px.pie(df, names='操作', hole=0.4, color='操作', color_discrete_map={'買進':'#2196f3', '觀察':'#bdbdbd', '追蹤':'#ffeb3b'})
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300); st.plotly_chart(fig, use_container_width=True)

except Exception as e: st.info(f"系統準備中... ({e})")
