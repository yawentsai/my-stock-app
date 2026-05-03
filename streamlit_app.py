import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# 頁面基本設定
st.set_page_config(page_title="標的追蹤戰情室 2.2", layout="wide")
st.title("🎯 個股追蹤戰情室 2.2")

# 建立資料庫連線
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 側邊欄：新增功能 ---
with st.sidebar:
    st.header("🖊️ 紀錄新觀察")
    user_input = st.text_area("在此貼上盤後筆記：", height=250)
    
    if st.button("🚀 解析並同步"):
        if user_input:
            try:
                target_match = re.search(r'[✅| ](.*?)[：|:]', user_input)
                target = target_match.group(1).strip() if target_match else "未知標的"
                change_match = re.search(r'\(.*?[+-](.*?)\%\)', user_input)
                change = float(change_match.group(1)) if change_match else 0
                if "-" in user_input and "(+" not in user_input: change = -abs(change)
                
                new_row = pd.DataFrame([{
                    "日期": datetime.now().strftime("%m/%d"),
                    "標的": target,
                    "操作": "買進" if "買" in user_input else ("觀察" if "觀察" in user_input else "紀錄"),
                    "漲跌%": change,
                    "盤後紀錄": user_input.replace('\n', ' ')
                }])
                
                existing_df = conn.read()
                updated_df = pd.concat([existing_df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success(f"🎉 {target} 已加入追蹤清單！")
                st.rerun()
            except:
                st.error("格式解析錯誤。")

# --- 主畫面 ---
try:
    df = conn.read().dropna(subset=['標的'])
    df['漲跌%'] = pd.to_numeric(df['漲跌%'], errors='coerce').fillna(0)
    
    # 1. 核心看板
    m1, m2 = st.columns(2)
    m1.metric("監控中標的數", f"{df['標的'].nunique()} 檔")
    win_rate = (len(df[df['漲跌%'] > 0]) / len(df) * 100) if len(df) > 0 else 0
    m2.metric("歷史預判勝率", f"{win_rate:.1f}%")

    st.divider()
    
    # 2. 勝率分佈
    st.subheader("📊 整體勝率分佈")
    df['類別'] = df['漲跌%'].apply(lambda x: '獲利' if x > 0 else ('虧損' if x < 0 else '持平'))
    fig = px.pie(df, names='類別', hole=0.4, 
                 color='類別', color_discrete_map={'獲利':'#ef5350', '虧損':'#26a69a', '持平':'#bdbdbd'})
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # 3. 按標的歸納的清單
    st.subheader("🔍 個股追蹤歷程")
    
    # 取得所有唯一標的，並按字母/筆畫排序
    unique_targets = sorted(df['標的'].unique())
    
    for target in unique_targets:
        # 篩選該標的的所有紀錄
        target_df = df[df['標的'] == target].sort_values(by='日期', ascending=False)
        last_change = target_df.iloc[0]['漲跌%']
        status_color = "#ef5350" if last_change > 0 else ("#26a69a" if last_change < 0 else "#bdbdbd")
        
        # 顯示標的小卡片
        with st.expander(f"📌 {target} (共 {len(target_df)} 筆紀錄 | 最新：{last_change}%)"):
            for _, row in target_df.iterrows():
                st.markdown(f"""
                    <div style="padding:10px; margin-bottom:5px; background:#f8f9fa; border-radius:5px; border-left: 3px solid {status_color};">
                        <span style="color:gray; font-size:0.8rem;">{row['日期']}</span> | 
                        <strong>{row['操作']}</strong> | {row['漲跌%']}% <br>
                        <small>{row['盤後紀錄']}</small>
                    </div>
                """, unsafe_allow_html=True)

except:
    st.info("系統就緒中...")
