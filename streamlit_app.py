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
for col in ['成本', '股數', '投入金額', '賣出價', '實現損益', '漲跌%']:
    existing_df[col] = pd.to_numeric(existing_df[col], errors='coerce').fillna(0.0)

# --- 側邊欄控制區 ---
with st.sidebar:
    st.header("⚡ 系統控制區")
    
    with st.expander("🌅 Step 1: 盤前計畫輸入", expanded=True):
        with st.form("pre_market", clear_on_submit=True):
            p_date = st.text_input("計畫日期", value=date.today().strftime("%m/%d"))
            p_action = st.selectbox("動作性質", ["觀察", "✅ 買進"])
            p_name = st.text_input("股票名稱*")
            p_symbol = st.text_input("代號 (選填)")
            p_pre = st.text_area("🔍 盤前核心計畫 (進場點、守護線、邏輯)")
            if st.form_submit_button("🚀 發布計畫") and p_name:
                new_row = pd.DataFrame([{"日期": p_date, "標的": p_name.strip(), "代號": p_symbol.strip(), "操作": "買進" if "買進" in p_action else "觀察", "成本": 0.0, "股數": 0, "投入金額": 0.0, "漲跌%": 0.0, "盤前觀察": p_pre, "盤後紀錄": "⏳ 等待收盤回饋...", "賣出價": 0.0, "實現損益": 0.0}])
                conn.update(data=pd.concat([existing_df, new_row], ignore_index=True)); st.cache_data.clear(); st.rerun()

    with st.expander("🌇 Step 2: 盤後結果統整"):
        waiting = existing_df[existing_df['盤後紀錄'] == "⏳ 等待收盤回饋..."]
        if not waiting.empty:
            with st.form("post_market", clear_on_submit=True):
                target = st.selectbox("選取標的進行統整", waiting.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1))
                res_pct = st.number_input("今日漲跌 / 結算結果 %", step=0.1)
                res_post = st.text_area("📝 盤後回饋 (執行狀況、紀律檢討)")
                if st.form_submit_button("💾 統整完成"):
                    sd, sn = target.split(" - ", 1)
                    idx = existing_df[(existing_df['日期']==sd) & (existing_df['標的']==sn)].index[0]
                    existing_df.at[idx, '漲跌%'] = float(res_pct)
                    existing_df.at[idx, '盤後紀錄'] = res_post
                    conn.update(data=existing_df); st.cache_data.clear(); st.rerun()
        else: st.info("目前所有計畫均已統整。")

# --- 主畫面顯示 ---
try:
    df = existing_df.dropna(subset=['標的']).copy()
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    
    # 結算看板 (省略 HTML，邏輯不變)
    # ... 看板代碼 ...

    t1, t2, t3, t4 = st.tabs(["💼 實單持股", "📰 即時新聞區", "📅 歷史日誌 (統整)", "🗂️ 個股深度追蹤"])
    
    with t3:
        # 💡 關鍵：只顯示已完成統整的資料
        completed = df[~df['盤後紀錄'].isin(["實單持倉中", "⏳ 等待收盤回饋...", "僅新聞追蹤"])].copy()
        if not completed.empty:
            for d in sorted(completed['日期'].unique(), reverse=True):
                st.markdown(f"#### 📅 {d}")
                for _, r in completed[completed['日期']==d].iterrows():
                    res_c = "#ef5350" if r['漲跌%'] > 0 else ("#26a69a" if r['漲跌%'] < 0 else "gray")
                    st.markdown(f"""
                    <div style="border-left:6px solid {res_c}; padding:15px; background:white; margin-bottom:20px; border-radius:8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee; border-left: 6px solid {res_c};">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                            <span style="font-weight:bold; font-size:1.2rem;">{r['標的']}</span>
                            <span style="color:{res_c}; font-weight:bold; font-size:1.2rem;">{r['漲跌%']:.1f}%</span>
                        </div>
                        <div style="background:#f8f9fa; padding:10px; border-radius:6px; margin-bottom:8px;">
                            <div style="color:#666; font-size:0.85rem; margin-bottom:4px;">🔍 盤前計畫</div>
                            <div style="color:#333; font-size:0.95rem; line-height:1.4;">{r['盤前觀察']}</div>
                        </div>
                        <div style="background:#fff; padding:10px; border-radius:6px; border:1px dashed #ddd;">
                            <div style="color:#666; font-size:0.85rem; margin-bottom:4px;">📝 盤後回饋</div>
                            <div style="color:#111; font-size:0.95rem; line-height:1.4;">{r['盤後紀錄']}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else: st.info("目前尚無統整紀錄。請先完成 Step 1 與 Step 2。")

    # ... 其他頁籤與底部勝率 (略) ...

except Exception as e: st.info(f"系統準備中... ({e})")
