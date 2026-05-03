import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# 頁面基本設定
st.set_page_config(page_title="交易分析系統 2.1", layout="wide")
st.title("📈 交易監控總表 2.1")

# 建立資料庫連線
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 側邊欄：輸入與同步功能 ---
with st.sidebar:
    st.header("🖊️ 新增盤後觀察")
    user_input = st.text_area("在此貼上妳的盤後筆記：", height=250)
    
    if st.button("🚀 點我解析並同步"):
        if user_input:
            try:
                # 自動解析逻辑
                target_match = re.search(r'[✅| ](.*?)[：|:]', user_input)
                target = target_match.group(1).strip() if target_match else "未知標的"
                
                change_match = re.search(r'\(.*?[+-](.*?)\%\)', user_input)
                change = float(change_match.group(1)) if change_match else 0
                if "-" in user_input and "(+" not in user_input: change = -abs(change)
                
                action = "買進" if "買" in user_input else ("觀察" if "觀察" in user_input else "紀錄")
                
                # 準備新資料
                new_row = pd.DataFrame([{
                    "日期": datetime.now().strftime("%m/%d"),
                    "標的": target,
                    "操作": action,
                    "漲跌%": change,
                    "盤後紀錄": user_input.replace('\n', ' ')
                }])
                
                # 讀取並更新
                existing_df = conn.read()
                updated_df = pd.concat([existing_df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success(f"🎉 {target} 已納入監控庫！")
                st.rerun()
            except Exception as e:
                st.error(f"解析稍微卡住了，請檢查格式。")

# --- 主畫面：視覺化戰情室 ---
try:
    # 讀取完整資料
    df = conn.read().dropna(subset=['標的'])
    df['漲跌%'] = pd.to_numeric(df['漲跌%'], errors='coerce').fillna(0)
    
    # 1. 頂部核心數據 (移除平均漲跌)
    m1, m2 = st.columns(2)
    m1.metric("累積監控標的", f"{len(df)} 檔")
    win_rate = (len(df[df['漲跌%'] > 0]) / len(df) * 100) if len(df) > 0 else 0
    m2.metric("預判勝率 (正回報)", f"{win_rate:.1f}%")

    st.divider()
    
    # 2. 勝率分佈圖
    st.subheader("🎯 勝率分佈圖")
    df['類別'] = df['漲跌%'].apply(lambda x: '獲利' if x > 0 else ('虧損' if x < 0 else '持平'))
    fig = px.pie(df, names='類別', hole=0.4, 
                 color='類別', color_discrete_map={'獲利':'#ef5350', '虧損':'#26a69a', '持平':'#bdbdbd'})
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # 3. 完整監控清單 (顯示每一檔股票)
    st.subheader("📑 完整監控歷史清單")
    
    # 由新到舊排列
    all_records = df.iloc[::-1]
    
    for _, row in all_records.iterrows():
        status_color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "#bdbdbd")
        with st.expander(f"📅 {row['日期']} | {row['標的']} | 漲跌：{row['漲跌%']}%"):
            st.markdown(f"""
                <div style="padding:10px; background:#f8f9fa; border-radius:8px; border-left: 5px solid {status_color};">
                    <strong>操作動作：</strong> {row['操作']}<br>
                    <strong>完整紀錄：</strong> {row['盤後紀錄']}
                </div>
            """, unsafe_allow_html=True)

except Exception as e:
    st.info("系統就緒中，請貼上第一筆觀測資料或檢查連線。")
