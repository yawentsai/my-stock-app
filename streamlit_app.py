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

# 初始化瀏覽器暫存記憶
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

# --- 資料庫讀取與強制字串清洗 ---
try:
    existing_df = conn.read(ttl=0)
    existing_df = existing_df.reset_index(drop=True) 
except:
    existing_df = pd.DataFrame(columns=['日期', '標的', '代號', '操作', '成本', '股數', '投入金額', '漲跌%', '盤前觀察', '盤後紀錄', '賣出價', '實現損益', '資料類型', '預判結果'])

if '資料類型' not in existing_df.columns:
    existing_df['資料類型'] = '戰報'
    mask_inventory = (existing_df['股數'] > 0) | (existing_df['盤後紀錄'] == '實單持倉中')
    existing_df.loc[mask_inventory, '資料類型'] = '庫存'

if '預判結果' not in existing_df.columns:
    existing_df['預判結果'] = '⏳ 待驗證'

existing_df['代號'] = existing_df['代號'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
existing_df['標的'] = existing_df['標的'].astype(str).str.strip()
existing_df['盤後紀錄'] = existing_df['盤後紀錄'].astype(str).str.strip()

def clean_date_format(d_str):
    try:
        if '/' in d_str:
            parts = d_str.split('/')
            return f"{int(parts[0])}/{int(parts[1])}"
        return d_str
    except:
        return d_str
existing_df['日期'] = existing_df['日期'].astype(str).apply(clean_date_format)

for col in ['成本', '股數', '投入金額', '賣出價', '實現損益', '漲跌%']:
    existing_df[col] = pd.to_numeric(existing_df[col], errors='coerce').fillna(0.0)

# 全自動滅毒機制
ghost_mask = (existing_df['盤後紀錄'] == '實單持倉中') & (existing_df['股數'] <= 0)
if ghost_mask.any():
    existing_df.loc[ghost_mask, '盤後紀錄'] = '異常作廢(股數歸零)'
    conn.update(data=existing_df)
    st.cache_data.clear()

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
                new_setting = pd.DataFrame([{"日期": f"{date.today().month}/{date.today().day}", "標的": "系統設定", "代號": "", "操作": "系統設定", "成本": 0.0, "股數": 0, "投入金額": new_capital, "漲跌%": 0.0, "盤前觀察": "", "盤後紀錄": "", "賣出價": 0.0, "實現損益": 0.0, "資料類型": "系統設定", "預判結果": "-"}])
                existing_df = pd.concat([existing_df, new_setting], ignore_index=True)
            conn.update(data=existing_df)
            st.cache_data.clear()
            st.rerun()
    st.divider()

    st.subheader("🔔 通知測試")
    if st.button("發送 LINE 測試通知"):
        if send_line_message("✅ 零股追蹤神器：連線測試成功！"):
            st.success("通知已發送，請檢查手機！")
        else:
            st.error("發送失敗，請檢查 Secrets 設定。")
    st.divider()

    with st.expander("🌅 Step 1: 盤前計畫"):
        with st.form("pre_m", clear_on_submit=True):
            p_date = st.text_input("日期", value=f"{date.today().month}/{date.today().day}")
            p_action = st.selectbox("性質", ["觀察", "✅ 買進"])
            p_name = st.text_input("股票名稱*")
            p_symbol = st.text_input("代號")
            p_pre = st.text_area("🔍 盤前觀點")
            if st.form_submit_button("🚀 發布"):
                new_r = pd.DataFrame([{"日期": p_date, "標的": p_name.strip(), "代號": p_symbol.strip(), "操作": "買進" if "買進" in p_action else "觀察", "成本": 0.0, "股數": 0, "投入金額": 0.0, "漲跌%": 0.0, "盤前觀察": p_pre, "盤後紀錄": "⏳ 等待更新...", "賣出價": 0.0, "實現損益": 0.0, "資料類型": "戰報", "預判結果": "⏳ 待驗證"}])
                conn.update(data=pd.concat([existing_df, new_r], ignore_index=True)); st.cache_data.clear(); st.rerun()

    with st.expander("✏️ 修正 / 刪除：戰報紀錄"):
        edit_df = existing_df[existing_df['資料類型'] == '戰報'].copy()
        if not edit_df.empty:
            edit_target = st.selectbox(
                "選取要處理的紀錄", 
                edit_df.index[::-1], 
                format_func=lambda x: f"{existing_df.at[x, '日期']} - {existing_df.at[x, '標的']} ({existing_df.at[x, '操作']})"
            )
            curr_date = existing_df.at[edit_target, '日期']
            curr_name = existing_df.at[edit_target, '標的']
            curr_symbol = existing_df.at[edit_target, '代號']
            curr_pre = existing_df.at[edit_target, '盤前觀察']
            curr_post = existing_df.at[edit_target, '盤後紀錄']
            
            with st.form("edit_fix_form"):
                new_date = st.text_input("修正日期", value=curr_date)
                new_name = st.text_input("修正標的名稱", value=curr_name)
                new_symbol = st.text_input("修正代號", value=curr_symbol)
                new_pre = st.text_area("修正盤前觀點", value=curr_pre, height=100)
                new_post = st.text_area("修正盤後紀錄", value=curr_post, height=100)
                
                col1, col2 = st.columns(2)
                with col1:
                    btn_update = st.form_submit_button("🔨 執行修改")
                with col2:
                    btn_delete = st.form_submit_button("🗑️ 刪除此紀錄")
                
                if btn_update:
                    existing_df.at[edit_target, '日期'] = new_date.strip()
                    existing_df.at[edit_target, '標的'] = new_name.strip()
                    existing_df.at[edit_target, '代號'] = new_symbol.strip()
                    existing_df.at[edit_target, '盤前觀察'] = new_pre
                    existing_df.at[edit_target, '盤後紀錄'] = new_post
                    conn.update(data=existing_df)
                    st.cache_data.clear()
                    st.rerun()
                elif btn_delete:
                    existing_df = existing_df.drop(edit_target)
                    conn.update(data=existing_df)
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.write("目前尚無戰報紀錄可修改。")

    with st.expander("🌇 Step 2: 盤後統整"):
        waiting = existing_df[(existing_df['資料類型'] == '戰報') & (existing_df['盤後紀錄'] == "⏳ 等待更新...")]
        if not waiting.empty:
            with st.form("post_m", clear_on_submit=True):
                target = st.selectbox("選取戰報", waiting.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1))
                final_action = st.selectbox("最終決策 (將覆寫盤前預設)", ["維持盤前規劃", "✅ 買進", "觀察"])
                pred_result = st.radio("本日預判驗證", ["✅ 預判命中", "❌ 預判失誤", "⏳ 待驗證"], horizontal=True)
                res_pct = st.number_input("漲跌 %", step=0.01, format="%.2f")
                res_post = st.text_area("📝 盤後回饋")
                
                if st.form_submit_button("💾 儲存戰報"):
                    sd, sn = target.split(" - ", 1)
                    idx = existing_df[(existing_df['日期']==sd) & (existing_df['標的']==sn) & (existing_df['資料類型']=='戰報')].index[0]
                    if final_action != "維持盤前規劃":
                        existing_df.at[idx, '操作'] = "買進" if "買進" in final_action else "觀察"
                    existing_df.at[idx, '漲跌%'] = float(res_pct)
                    existing_df.at[idx, '盤後紀錄'] = res_post
                    existing_df.at[idx, '預判結果'] = pred_result.split(" ")[0] + " " + pred_result.split(" ")[1] 
                    conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

    st.divider()

    with st.expander("🛒 實單庫存：買入 / 刪除登錄"):
        tb_buy, tb_del = st.tabs(["✅ 買入登錄", "🗑️ 刪除誤植"])
        with tb_buy:
            with st.form("buy_f"):
                br_date = st.date_input("日期", value=date.today())
                br_n, br_s = st.text_input("名稱"), st.text_input("代號")
                br_p = st.number_input("均價", min_value=0.0); br_q = st.number_input("股數", min_value=1, value=100)
                if st.form_submit_button("✅ 加入持倉"):
                    br_n = br_n.strip()
                    br_s = br_s.strip()
                    clean_br_date = f"{br_date.month}/{br_date.day}"
                    
                    match_cond = (existing_df['資料類型'] == '庫存') & (existing_df['盤後紀錄'] == "實單持倉中") & ((existing_df['標的'] == br_n) | ((existing_df['代號'] == br_s) & (br_s != "")))
                    active_idx = existing_df[match_cond].index
                    
                    if not active_idx.empty:
                        idx = active_idx[0]
                        old_q = existing_df.at[idx, '股數']
                        old_amt = existing_df.at[idx, '投入金額']
                        new_q = old_q + int(br_q)
                        new_amt = old_amt + (float(br_p) * int(br_q))
                        new_p = new_amt / new_q  
                        existing_df.loc[idx, '股數'] = new_q
                        existing_df.loc[idx, '投入金額'] = new_amt
                        existing_df.loc[idx, '成本'] = new_p
                        existing_df.loc[idx, '日期'] = clean_br_date 
                        conn.update(data=existing_df)
                    else:
                        new_r = pd.DataFrame([{"日期": clean_br_date, "標的": br_n, "代號": br_s, "操作": "庫存", "成本": float(br_p), "股數": int(br_q), "投入金額": br_p*br_q, "漲跌%": 0.0, "盤前觀察": "", "盤後紀錄": "實單持倉中", "賣出價":0.0, "實現損益":0.0, "資料類型":"庫存", "預判結果":"-"}])
                        conn.update(data=pd.concat([existing_df, new_r], ignore_index=True))
                        
                    st.cache_data.clear(); st.rerun()
        with tb_del:
            active_h_del = existing_df[(existing_df['資料類型'] == '庫存') & (existing_df['盤後紀錄'] == "實單持倉中")]
            if not active_h_del.empty:
                with st.form("del_buy_f"):
                    st.info("⚠️ 僅用於刪除『輸入錯誤』的紀錄，若是正常獲利/停損了結，請使用下方『賣出結算』。")
                    del_sel = st.selectbox("選取要刪除的持倉", active_h_del.apply(lambda x: f"{x.name} | {x['日期']} - {x['標的']} (均價:{x['成本']:.2f})", axis=1))
                    if st.form_submit_button("🗑️ 確認刪除"):
                        idx_to_drop = int(del_sel.split(" | ")[0])
                        existing_df = existing_df.drop(idx_to_drop)
                        conn.update(data=existing_df); st.cache_data.clear(); st.rerun()
            else:
                st.write("目前無持倉可刪除。")

    with st.expander("💸 實單庫存：賣出結算"):
        active_h = existing_df[(existing_df['資料類型'] == '庫存') & (existing_df['盤後紀錄'] == "實單持倉中")]
        if not active_h.empty:
            with st.form("sell_f"):
                sel = st.selectbox("選取結算對象", active_h.apply(lambda x: f"{x['日期']} - {x['標的']}", axis=1))
                sd_sel, sn_sel = sel.split(" - ", 1)
                curr_row = existing_df[(existing_df['日期']==sd_sel) & (existing_df['標的']==sn_sel) & (existing_df['資料類型']=='庫存')].iloc[0]
                
                curr_q = int(curr_row['股數'])
                safe_max_q = max(1, curr_q)
                
                sr_p = st.number_input("賣出單價", min_value=0.0)
                sr_q = st.number_input(f"賣出股數 (真實持有: {curr_q})", min_value=1, max_value=safe_max_q, value=safe_max_q)
                
                submitted = st.form_submit_button("💰 結算獲利 (純算帳)")
                
                if submitted:
                    if curr_q <= 0:
                        st.error(f"🚨 結算失敗！「{sn_sel}」的實際庫存為 0。系統將在重整後自動作廢此紀錄。")
                    else:
                        idx = existing_df[(existing_df['日期']==sd_sel) & (existing_df['標的']==sn_sel) & (existing_df['資料類型']=='庫存')].index[0]
                        cp, q_orig = existing_df.at[idx, '成本'], existing_df.at[idx, '股數']
                        
                        if sr_q < q_orig:
                            new_sold = existing_df.loc[[idx]].copy()
                            new_sold['股數'], new_sold['投入金額'], new_sold['賣出價'] = sr_q, cp * sr_q, sr_p
                            new_sold['實現損益'], new_sold['盤後紀錄'] = (sr_p - cp) * sr_q, "已結算(減碼)"
                            existing_df.at[idx, '股數'] = q_orig - sr_q
                            existing_df.at[idx, '投入金額'] = cp * (q_orig - sr_q)
                            existing_df = pd.concat([existing_df, new_sold], ignore_index=True)
                        else:
                            existing_df.at[idx, '賣出價'], existing_df.at[idx, '實現損益'] = sr_p, (sr_p - cp) * q_orig
                            existing_df.at[idx, '盤後紀錄'] = "已結算(清倉)"
                        
                        conn.update(data=existing_df); st.cache_data.clear(); st.rerun()

# --- 主畫面顯示 ---
try:
    df = existing_df[existing_df['操作'] != '系統設定'].dropna(subset=['標的']).copy()
    df['標的'] = df['標的'].astype(str).str.replace(r'\d+', '', regex=True).str.strip()
    
    inv_df = df[df['資料類型'] == '庫存']
    total_realized = inv_df['實現損益'].sum()
    active_df = inv_df[inv_df['盤後紀錄'] == '實單持倉中']
    
    total_unrealized = 0; active_holdings = []; ready_to_sell = []
    for _, row in active_df.iterrows():
        cp = get_live_price(row['代號'])
        p_pct = ((cp - row['成本']) / row['成本']) * 100 if cp else 0.0
        p_twd = (cp - row['成本']) * row['股數'] if cp else 0.0
        total_unrealized += p_twd
        active_holdings.append({'日期': row['日期'], '標的': row['標的'], '代號': row['代號'], '均價': row['成本'], '股數': row['股數'], '現價': cp if cp else "...", '損益金額': p_twd, '損益率%': p_pct})
        
        if p_pct >= 5.0: ready_to_sell.append({'name': row['標的'], 'symbol': row['代號'], 'pct': p_pct})
    
    total_profit = total_realized + total_unrealized
    equity = INITIAL_CAPITAL + total_profit
    roi_pct = (total_profit / INITIAL_CAPITAL) * 100 if INITIAL_CAPITAL > 0 else 0.0
    target_count = len(ready_to_sell)

    realized_c = "#2e7d32" if total_realized >= 0 else "#c62828"
    unrealized_c = "#2e7d32" if total_unrealized >= 0 else "#c62828"
    profit_c = "#1b5e20" if total_profit >= 0 else "#b71c1c"
    profit_bg = "#e8f5e9" if total_profit >= 0 else "#ffebee"

    st.markdown("### 🏦 真實資產結算看板")
    st.markdown(f"""
    <div class="dashboard-grid">
        <div class="metric-card"><div class="metric-label">投入總本金</div><div class="metric-value">${INITIAL_CAPITAL:,.0f}</div></div>
        <div class="metric-card"><div class="metric-label">已實現獲利</div><div class="metric-value" style="color:{realized_c};">${total_realized:,.0f}</div></div>
        <div class="metric-card"><div class="metric-label">未實現獲利</div><div class="metric-value" style="color:{unrealized_c};">${total_unrealized:,.0f}</div></div>
        <div class="metric-card" style="background:{profit_bg}; border-color:{profit_c}22;"><div class="metric-label" style="color:{profit_c};">🎯 總獲利 %</div><div class="metric-value" style="color:{profit_c};">{roi_pct:.2f}%</div></div>
        <div class="metric-card" style="background:#fff3e0;"><div class="metric-label" style="color:#e65100;">達 5% 停利檔數</div><div class="metric-value" style="color:#e65100;">{target_count} 檔</div></div>
        <div class="metric-card"><div class="metric-label">總資產權益</div><div class="metric-value">${equity:,.0f}</div></div>
    </div>
    """, unsafe_allow_html=True)

    if ready_to_sell:
        items_html = "".join([f"<div style='display: flex; justify-content: space-between; border-bottom: 1px dashed #ffcdd2; padding: 6px 0;'><span style='font-weight:bold; color:#b71c1c;'>{item['name']} ({item['symbol']})</span><span style='font-weight:bold; color:#c62828;'>+{item['pct']:.2f}%</span></div>" for item in ready_to_sell])
        st.markdown(f"""<div class="status-box" style="background-color:#ffebee; border:2px solid #ef5350; margin-bottom:20px;">🚨 停利標準已達標 (共 {target_count} 檔等待結算)：<br>{items_html}</div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="status-box" style="background-color:#e8f5e9; color:#2e7d32; border:1px dashed #4caf50;">✅ 目前持股獲利尚未達 5% 停利標準，請繼續耐心持有。</div>""", unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["💼 實單持股", "📅 歷史日誌 (戰報專區)", "🗂️ 個股深度追蹤"])
    
    with t1:
        if active_holdings:
            st.dataframe(pd.DataFrame(active_holdings), use_container_width=True, hide_index=True, column_config={
                "現價": st.column_config.NumberColumn(format="%.2f"),
                "均價": st.column_config.NumberColumn(format="%.2f"),
                "損益金額": st.column_config.NumberColumn(format="%.0f"),
                "損益率%": st.column_config.NumberColumn(format="%.2f%%")
            })
        else: st.info("目前無持倉。")

    war_reports = df[df['資料類型'] == '戰報'].copy()
    
    with t2:
        if not war_reports.empty:
            def parse_date_for_sort(d_str):
                try: return datetime.strptime(d_str, "%m/%d")
                except: return datetime.min
            for d in sorted(war_reports['日期'].unique(), key=parse_date_for_sort, reverse=True):
                with st.expander(f"🗓️ {d} 操盤戰報", expanded=(d == war_reports['日期'].max())):
                    for idx, r in war_reports[war_reports['日期'] == d].iterrows():
                        res_c = "#ef5350" if r['漲跌%'] > 0 else ("#26a69a" if r['漲跌%'] < 0 else "gray")
                        bg = "#ef5350" if "買進" in r['操作'] else "#bdbdbd"
                        
                        # 💡 確保排版完全不變，隱藏預判結果的文字標籤
                        st.markdown(f"""
                        <div style="border-left:6px solid {res_c}; padding:15px; background:white; margin-bottom:12px; border-radius:8px; border: 1px solid #eee;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                                <div>
                                    <span style='background-color:{bg}; color:white; padding:2px 8px; border-radius:4px; font-size:0.8rem;'>{r['操作']}</span>
                                    <strong style="margin-left:5px;">{r['標的']}</strong>
                                </div>
                                <div>
                                    <span style="color:{res_c}; font-weight:bold;">{r['漲跌%']:.2f}%</span>
                                </div>
                            </div>
                            <div style="background:#f8f9fa; padding:10px; border-radius:6px; margin-bottom:5px; font-size:0.95rem; text-align: justify; line-height: 1.6;">
                                🔍 <b>盤前：</b>{format_list_text(r['盤前觀察'])}
                            </div>
                            <div style="background:#fff; padding:10px; border-radius:6px; border:1px dashed #ddd; font-size:0.95rem; text-align: justify; line-height: 1.6;">
                                📝 <b>盤後：</b>{format_list_text(r['盤後紀錄'])}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    with t3:
        if not war_reports.empty:
            for t in sorted(war_reports['標的'].unique()):
                t_df = war_reports[war_reports['標的'] == t].copy()
                t_df['sort_date'] = pd.to_datetime(t_df['日期'].astype(str) + f'/{date.today().year}', format='%m/%d/%Y', errors='coerce')
                t_df = t_df.sort_values(by='sort_date', ascending=False).drop(columns=['sort_date'])
                with st.expander(f"📌 {t} (戰報紀錄：{len(t_df)} 筆)"):
                    for idx, row in t_df.iterrows():
                        c = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "#bdbdbd")
                        
                        # 💡 同樣隱藏預判結果的文字標籤
                        st.markdown(f"""
                        <div style='border-left:5px solid {c}; padding:10px; background:#f8f9fa; margin-bottom:10px; border-radius:4px;'>
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <b>{row['日期']} | <span style='color:{c};'>{row['漲跌%']:.2f}%</span></b>
                            </div>
                            <div style='margin-top:5px; font-size:0.9rem; text-align: justify; line-height: 1.6; color:#444;'>
                                🔍 <b>盤前：</b>{format_list_text(row['盤前觀察'])}
                            </div>
                            <div style='margin-top:5px; font-size:0.9rem; text-align: justify; line-height: 1.6; color:#444;'>
                                📝 <b>盤後：</b>{format_list_text(row['盤後紀錄'])}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    st.divider()
    
    valid_preds = war_reports[war_reports['預判結果'].str.contains('命中|失誤', na=False, regex=True)]
    if not valid_preds.empty:
        hits = len(valid_preds[valid_preds['預判結果'].str.contains('命中')])
        w_r = (hits / len(valid_preds)) * 100
        
        st.markdown(f"<div><span style='font-size:1.1rem; color:#555;'>🎯 盤前推演真實命中率</span><br><span style='font-size:2.5rem; font-weight:bold; color:#2196f3;'>{w_r:.1f}%</span></div>", unsafe_allow_html=True)
        
        fig = px.pie(valid_preds, names='預判結果', hole=0.4, color='預判結果', color_discrete_map={'✅ 命中':'#2196f3', '❌ 失誤':'#ef5350'})
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(f"<div><span style='font-size:1.1rem; color:#555;'>🎯 盤前推演真實命中率</span><br><span style='font-size:2.5rem; font-weight:bold; color:#2196f3;'>0.0%</span><br><small style='color:gray;'>尚無已驗證的盤後紀錄</small></div>", unsafe_allow_html=True)

except Exception as e: st.info(f"系統準備中... ({e})")
