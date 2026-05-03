import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# 頁面基本設定
st.set_page_config(page_title="交易分析系統 2.0", layout="wide")
st.title("📈 交易分析儀表板 2.0")

# 建立資料庫連線
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 側邊欄：輸入與同步功能 ---
with st.sidebar:
    st.header("🖊️ 新增盤後觀察")
    user_input = st.text_area("在此貼上妳的盤後筆記：", height=250)
    
    if st.button("🚀 點我解析並同步"):
        if user_input:
            try:
                # 幫妳寫好的自動解析逻辑
                target = re.search(r'[✅| ](.*?)[：|:]', user_input).group(1).strip()
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
                    "盤後紀錄": user_input[:50] + "..."
                }])
                
                # 讀取並更新
                existing_df = conn.read()
                updated_df = pd.concat([existing_df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success(f"🎉 {target} 已飛進試算表了！")
            except Exception as e:
                st.error(f"解析稍微卡住了，請確認筆記格式喔！")

# --- 主畫面：視覺化戰情室 ---
try:
    df = conn.read()
    df['漲跌%'] = pd.to_numeric(df['漲跌%'], errors='coerce').fillna(0)
    
    # 頂部數據看板
    m1, m2, m3 = st.columns(3)
    m1.metric("累積監控標的", f"{len(df)} 檔")
    win_rate = (len(df[df['漲跌%'] > 0]) / len(df) * 100) if len(df) > 0 else 0
    m2.metric("預判勝率 (正回報)", f"{win_rate:.1f}%")
    m3.metric("標的平均漲跌", f"{df['漲跌%'].mean():.2f}%")

    st.divider()
    
    # 圖表與最近紀錄
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("🎯 勝率分佈圖")
        df['類別'] = df['漲跌%'].apply(lambda x: '獲利' if x > 0 else ('虧損' if x < 0 else '持平'))
        fig = px.pie(df, names='類別', hole=0.4, 
                     color='類別', color_discrete_map={'獲利':'#ef5350', '虧損':'#26a69a', '持平':'#bdbdbd'})
        st.plotly_chart(fig, use_container_width=True)
    
    with c2:
        st.subheader("📝 最近 5 筆動態")
        for _, row in df.tail(5).iloc[::-1].iterrows():
            c = "#ef5350" if row['漲跌%'] > 0 else "#26a69a"
            st.markdown(f'''
                <div style="border-left:5px solid {c};padding:12px;margin-bottom:10px;background:#f8f9fa;border-radius:8px;">
                    <strong>{row["日期"]} {row["標的"]}</strong> | <span style="color:{c};">{row["漲跌%"]}%</span><br>
                    <small style="color:gray;">{row["盤後紀錄"]}</small>
                </div>
            ''', unsafe_allow_html=True)
except:
    st.info("資料庫連線中... 請確認 Secrets 設定是否正確。")
