import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import requests
import re

# 1. 基礎設定與手機版網格鎖定
st.set_page_config(page_title="零股追蹤神器", layout="wide")
st.title("🚀 零股追蹤神器")

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

def format_list_text(text):
    if not isinstance(text, str) or not text.strip(): return ""
    text = text.replace('\n', '<br>')
    text = re.sub(r'(?<!^)(?<!<br>)\s*(\b\d+\.\s*)', r'<br>\1', text)
    return f'<div style="padding-left: 1.4em; text-indent: -1.4em; margin-top: 4px;">{text}</div>'

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

# 初始化本金設定
if 'capital' not in st.session_state:
    st.session_state['capital'] = 150000

st_autorefresh(interval=60000, limit=1000, key="global_v87_final")

conn = st.connection("gsheets", type=GSheetsConnection)

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

# --- 資料庫讀取與清洗 ---
try:
    existing_df = conn.read(ttl=0)
    existing_df = existing_df.reset_index(drop=True) 
except:
    existing_df = pd.DataFrame(columns=['日期', '標的', '代號', '操作', '成本', '股數', '投入金額', '漲跌%', '盤前觀察', '盤後紀錄', '賣出價', '實現損益'])

existing_df['代號'] = existing_df['代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
existing_df['標的'] = existing_df['標的'].astype(str).str.strip()
existing_df['盤後紀錄'] = existing_df['盤後紀錄'].astype(str).str.strip()

def clean_date_format(d_str):
    try:
        if '/' in d_str:
            parts = d_str.split('/')
            return f"{int(parts[0])}/{int(parts[1])}"
        return d_str
    except: return d_str
existing_df['日期'] = existing_df['日期'].astype(str).apply(clean_date_format)

for col in ['成本', '股數', '投入金額', '賣出價', '實現損益', '漲跌%']:
    existing_df[col] = pd.to_numeric(existing_df[col], errors='coerce').fillna(0.0)

# 💡 核心機制：確保本金定錨
settings_idx = existing_df[existing_df['操作'] == '系統設定'].index
if not settings_idx.empty:
    INITIAL_CAPITAL = float(existing_df.loc[settings_idx[-1], '投入金額'])
else:
    INITIAL_CAPITAL = 150000.0

with st.sidebar:
    st.header("⚡ 系統控制區")
    
    st.subheader("💰 資金控管")
    with st.form("capital_form"):
        new_capital = st.number_input("當前總本金 (可隨時增減)", min_value=0.0, value=INITIAL_CAPITAL, step=10000.0)
        if st.form_submit_button("✅ 確認修改"):
            if not settings_idx.empty:
                existing_df.loc[settings_idx[-1], '投入金額'] = new_capital
            else:
                new_setting = pd.DataFrame([{"日期": f"{date.today().month}/{date.today().day}", "標的": "系統設定", "代號": "", "操作": "系統設定", "成本": 0.0, "股數": 0, "投入金額": new_capital, "漲跌%": 0.0, "盤前觀察": "", "盤後紀錄": "", "賣出價": 0.0, "實現損益": 0.0}])
                existing_df = pd.concat([existing_df, new_setting], ignore_index=True)
            conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

    with st.expander("🌅 Step 1: 盤前計畫"):
        with st.form("pre_m", clear_on_submit=True):
            p_date = st.text_input("日期", value=f"{date.today().month}/{date.today().day}")
            p_action = st.selectbox("性質", ["觀察", "✅ 買進"])
            p_name = st.text_input("股票名稱*")
            p_symbol = st.text_input("代號")
            p_pre = st.text_area("🔍 盤前觀點")
            if st.form_submit_button("🚀 發布"):
                new_r = pd.DataFrame([{"日期": p_date, "標的": p_name.strip(), "代號": p_symbol.strip(), "操作": "買進" if "買進" in p_action else "觀察", "成本": 0.0, "股數": 0, "投入金額": 0.0, "漲跌%": 0.0, "盤前觀察": p_pre, "盤後紀錄": "⏳ 等待更新...", "賣出價": 0.0, "實現損益": 0.0}])
                conn.update(data=pd.concat([existing_df, new_r], ignore_index=True)); st.cache_data.clear(); st.rerun()

    with st.expander("✏️ 修正：內容微調"):
        if not existing_df.empty:
            edit_df = existing_df[existing_df['操作'] != '系統設定'].copy()
            if not edit_df.empty:
                edit_target = st.selectbox("選取修正紀錄", edit_df.index[::-1], format_func=lambda x: f"{existing_df.at[x, '日期']} - {existing_df.at[x, '標的']}")
                with st.form("edit_fix_form"):
                    n_d = st.text_input("修正日期", value=existing_df.at[edit_target, '日期'])
                    n_n = st.text_input("修正標的", value=existing_df.at[edit_target, '標的'])
                    n_s = st.text_input("修正代號", value=existing_df.at[edit_target, '代號'])
                    n_pre = st.text_area("修正盤前", value=existing_df.at[edit_target, '盤前觀察'])
                    n_post = st.text_area("修正盤後", value=existing_df.at[edit_target, '盤後紀錄'])
                    if st.form_submit_button("🔨 覆蓋修正"):
                        existing_df.at[edit_target, '日期'], existing_df.at[edit_target, '標的'], existing_df.at[edit_target, '代號'], existing_df.at[edit_target, '盤前觀察'], existing_df.at[edit_target, '盤後紀錄'] = n_d, n_n, n_s, n_pre, n_post
                        conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

    with st.expander("🌇 Step 2: 盤後統整"):
        waiting = existing_df[existing_df['盤後紀錄'] == "⏳ 等待更新..."]
        if not waiting.empty:
            with st.form("post_m", clear_on_submit=True):
                target = st.selectbox("選取標的", waiting.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1))
                final_action = st.selectbox("最終決策", ["維持盤前規劃", "✅ 買進", "觀察"])
                res_pct = st.number_input("漲跌 %", step=0.01, format="%.2f")
                res_post = st.text_area("📝 盤後回饋")
                if st.form_submit_button("💾 儲存"):
                    sd, sn = target.split(" - ", 1)
                    idx = existing_df[(existing_df['日期']==sd) & (existing_df['標的']==sn)].index[0]
                    if final_action != "維持盤前規劃": existing_df.at[idx, '操作'] = "買進" if "買進" in final_action else "觀察"
                    existing_df.at[idx, '漲跌%'], existing_df.at[idx, '盤後紀錄'] = float(res_pct), res_post
                    conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

    st.divider()

    with st.expander("🛒 實單庫存：買入 / 刪除"):
        tb_buy, tb_del = st.tabs(["✅ 買入登錄", "🗑️ 刪除誤植"])
        with tb_buy:
            with st.form("buy_f"):
                br_date = st.date_input("日期", value=date.today())
                br_n, br_s = st.text_input("名稱"), st.text_input("代號")
                br_p = st.number_input("均價", min_value=0.0); br_q = st.number_input("股數", min_value=1, value=100)
                if st.form_submit_button("✅ 加入持倉"):
                    clean_br_date = f"{br_date.month}/{br_date.day}"
                    match_cond = (existing_df['盤後紀錄'] == "實單持倉中") & ((existing_df['標的'] == br_n) | ((existing_df['代號'] == br_s) & (br_s != "")))
                    active_idx = existing_df[match_cond].index
                    if not active_idx.empty:
                        idx = active_idx[0]; old_q = existing_df.at[idx, '股數']; old_amt = existing_df.at[idx, '投入金額']
                        new_q = old_q + int(br_q); new_amt = old_amt + (float(br_p) * int(br_q))
                        existing_df.loc[idx, '股數'], existing_df.loc[idx, '投入金額'], existing_df.loc[idx, '成本'], existing_df.loc[idx, '日期'] = new_q, new_amt, (new_amt / new_q), clean_br_date
                        conn.update(data=existing_df)
                    else:
                        new_r = pd.DataFrame([{"日期": clean_br_date, "標的": br_n, "代號": br_s, "操作": "買進", "成本": float(br_p), "股數": int(br_q), "投入金額": br_p*br_q, "漲跌%": 0.0, "盤後紀錄": "實單持倉中"}])
                        conn.update(data=pd.concat([existing_df, new_r], ignore_index=True))
                    st.cache_data.clear(); st.rerun()
        with tb_del:
            active_h_del = existing_df[existing_df['盤後紀錄'] == "實單持倉中"]
            if not active_h_del.empty:
                with st.form("del_buy_f"):
                    del_sel = st.selectbox("選取要刪除的持倉", active_h_del.apply(lambda x: f"{x.name} | {x['日期']} - {x['標的']} (均價:{x['成本']:.2f})", axis=1))
                    if st.form_submit_button("🗑️ 確認刪除"):
                        idx_to_drop = int(del_sel.split(" | ")[0]); existing_df = existing_df.drop(idx_to_drop)
                        conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

    with st.expander("💸 實單庫存：賣出結算"):
        active_h = existing_df[existing_df['盤後紀錄'] == "實單持倉中"]
        if not active_h.empty:
            with st.form("sell_f"):
                sel = st.selectbox("選取結算對象", active_h.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1))
                sd_sel, sn_sel = sel.split(" - ", 1)
                curr_row = existing_df[(existing_df['日期']==sd_sel) & (existing_df['標的']==sn_sel)].iloc[0]
                curr_q = int(curr_row['股數']); safe_max_q = max(1, curr_q)
                sr_p = st.number_input("賣出單價", min_value=0.0)
                sr_q = st.number_input(f"賣出股數 (真實持有: {curr_q})", min_value=1, max_value=safe_max_q, value=safe_max_q)
                sr_n = st.text_input("出場筆記")
                if st.form_submit_button("💰 結算獲利"):
                    if curr_q <= 0: st.error("🚨 實際庫存為 0，請至『🗑️ 刪除誤植』處理。")
                    else:
                        idx = existing_df[(existing_df['日期']==sd_sel) & (existing_df['標的']==sn_sel)].index[0]
                        cp, q_orig = existing_df.at[idx, '成本'], existing_df.at[idx, '股數']
                        if sr_q < q_orig:
                            new_sold = existing_df.loc[[idx]].copy()
                            new_sold['股數'], new_sold['投入金額'], new_sold['賣出價'], new_sold['實現損益'], new_sold['漲跌%'], new_sold['盤後紀錄'] = sr_q, cp * sr_q, sr_p, (sr_p - cp) * sr_q, ((sr_p - cp)/cp)*100, f"減碼：{sr_n}"
                            existing_df.at[idx, '股數'], existing_df.at[idx, '投入金額'] = q_orig - sr_q, cp * (q_orig - sr_q)
                            existing_df = pd.concat([existing_df, new_sold], ignore_index=True)
                        else:
                            existing_df.at[idx, '賣出價'], existing_df.at[idx, '實現損益'], existing_df.at[idx, '漲跌%'], existing_df.at[idx, '盤後紀錄'] = sr_p, (sr_p - cp) * q_orig, ((sr_p - cp)/cp)*100, f"清倉：{sr_n}"
                        conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

# --- 主畫面顯示 ---
try:
    df = existing_df[existing_df['操作'] != '系統設定'].dropna(subset=['標的']).copy()
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    
    total_realized = df['實現損益'].sum(); active_df = df[df['盤後紀錄'] == '實單持倉中']
    total_unrealized = 0; active_holdings = []; ready_to_sell = []
    for _, row in active_df.iterrows():
        cp = get_live_price(row['代號']); p_pct = ((cp - row['成本']) / row['成本']) * 100 if cp else 0.0
        p_twd = (cp - row['成本']) * row['股數'] if cp else 0.0; total_unrealized += p_twd
        active_holdings.append({'日期': row['日期'], '標的': row['標的'], '代號': row['代號'], '均價': row['成本'], '股數': row['股數'], '現價': cp if cp else "...", '損益金額': p_twd, '損益率%': p_pct})
        if p_pct >= 5.0: ready_to_sell.append({'name': row['標的'], 'symbol': row['代號'], 'pct': p_pct})
    
    total_profit = total_realized + total_unrealized; equity = INITIAL_CAPITAL + total_profit
    roi_pct = (total_profit / INITIAL_CAPITAL) * 100 if INITIAL_CAPITAL > 0 else 0.0
    target_count = len(ready_to_sell)

    st.markdown(f"""<div class="dashboard-grid"><div class="metric-card"><div class="metric-label">投入總本金</div><div class="metric-value">${INITIAL_CAPITAL:,.0f}</div></div><div class="metric-card"><div class="metric-label">已實現獲利</div><div class="metric-value">${total_realized:,.0f}</div></div><div class="metric-card"><div class="metric-label">未實現獲利</div><div class="metric-value">${total_unrealized:,.0f}</div></div><div class="metric-card"><div class="metric-label">🎯 總獲利 %</div><div class="metric-value">{roi_pct:.2f}%</div></div><div class="metric-card" style="background:#fff3e0;"><div class="metric-label">達 5% 停利檔數</div><div class="metric-value">{target_count} 檔</div></div><div class="metric-card"><div class="metric-label">總資產權益</div><div class="metric-value">${equity:,.0f}</div></div></div>""", unsafe_allow_html=True)

    if ready_to_sell:
        items_html = "".join([f"<div><b>{item['name']} ({item['symbol']})</b> +{item['pct']:.2f}%</div>" for item in ready_to_sell])
        st.markdown(f"""<div class="status-box" style="background-color:#ffebee; border:2px solid #ef5350;">🚨 停利標準已達標：<br>{items_html}</div>""", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["💼 實單持股", "📅 歷史日誌 (全紀錄)", "🗂️ 個股深度追蹤"])
    with t1:
        if active_holdings: st.dataframe(pd.DataFrame(active_holdings), use_container_width=True, hide_index=True)
        else: st.info("目前無持倉。")

    with t2:
        def parse_date_for_sort(d_str):
            try: return datetime.strptime(d_str, "%m/%d")
            except: return datetime.min
        for d in sorted(df['日期'].unique(), key=parse_date_for_sort, reverse=True):
            with st.expander(f"🗓️ {d} 操盤戰報", expanded=(d == df['日期'].max())):
                for idx, r in df[df['日期'] == d].iterrows():
                    res_c = "#ef5350" if r['漲跌%'] > 0 else ("#26a69a" if r['漲跌%'] < 0 else "gray")
                    st.markdown(f"""<div style="border-left:6px solid {res_c}; padding:10px; background:white; border-radius:8px; border: 1px solid #eee; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between;">
                            <span><b>{r['操作']} - {r['標的']}</b></span>
                            <span style="color:{res_c};"><b>{r['漲跌%']:.2f}%</b></span>
                        </div>
                        <div style="font-size:0.9rem; background:#f8f9fa; padding:5px; border-radius:4px;">🔍 {format_list_text(r['盤前觀察'])}</div>
                        <div style="font-size:0.9rem; padding:5px;">📝 {format_list_text(r['盤後紀錄'])}</div>
                    </div>""", unsafe_allow_html=True)
                    if st.button("🗑️ 刪除", key=f"del_t2_{idx}"):
                        existing_df = existing_df.drop(idx); conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

    with t3:
        for t in sorted(df['標的'].unique()):
            t_df = df[df['標的'] == t].copy()
            t_df['sort_date'] = pd.to_datetime(t_df['日期'].astype(str) + f'/{date.today().year}', format='%m/%d/%Y', errors='coerce')
            t_df = t_df.sort_values(by='sort_date', ascending=False)
            with st.expander(f"📌 {t} (歷史紀錄：{len(t_df)} 筆)"):
                for idx, row in t_df.iterrows():
                    st.markdown(f"""<div style="border-bottom:1px dashed #ddd; padding:5px;">
                        <b>{row['日期']} | {row['操作']} | {row['盤後紀錄']}</b><br>
                        <small>🔍 {format_list_text(row['盤前觀察'])}</small>
                    </div>""", unsafe_allow_html=True)
                    if st.button("🗑️ 移除此筆", key=f"del_t3_{idx}"):
                        existing_df = existing_df.drop(idx); conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

    st.divider()
    c_buy = df[df['操作'] == '買進']
    w_r = (len(c_buy[c_buy['漲跌%'] > 0]) / len(c_buy) * 100) if not c_buy.empty else 0.0
    st.markdown(f"<div>📊 實際預判勝率: <span style='font-size:1.5rem; color:#2196f3;'>{w_r:.1f}%</span></div>", unsafe_allow_html=True)

except Exception as e: st.info(f"系統準備中... ({e})")
