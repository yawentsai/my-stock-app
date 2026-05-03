import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

st.set_page_config(page_title="個股追蹤戰情室 2.5", layout="wide")
st.title("🎯 個股追蹤戰情室 2.5")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 側邊欄：精密解析功能 ---
with st.sidebar:
    st.header("📥 批次同步筆記")
    user_input = st.text_area("在此貼上整理好的筆記：", height=400)
    
    if st.button("🚀 開始精密解析"):
        if user_input:
            try:
                blocks = re.split(r'\n(?=✅|[\u4e00-\u9fa5]{2,4}[:：])', user_input)
                new_data = []
                current_date = datetime.now().strftime("%m/%d")

                for block in blocks:
                    block = block.strip()
                    if not block: continue
                    
                    # 更新日期
                    date_match = re.search(r'(\d{1,2}/\d{1,2})', block)
                    if date_match: current_date = date_match.group(1)

                    # 提取標的 (嚴格限制長度，避免誤抓描述)
                    lines = block.split('\n')
                    header = lines[0]
                    if "：" in header or ":" in header:
                        target_part = re.split(r'[：:]', header)[0].replace('✅', '').strip()
                        target_clean = re.sub(r'\d+', '', target_part).strip()
                        
                        # 如果標的名稱太長，代表抓錯了，略過
                        if len(target_clean) > 5: continue
                        
                        # 拆分盤前與盤後
                        full_content = " ".join(lines)
                        obs_part = ""
                        rec_part = ""
                        if "👉🏻" in full_content:
                            parts = full_content.split("👉🏻")
                            obs_part = parts[0].split("：", 1)[-1].strip() if "：" in parts[0] else parts[0]
                            rec_part = parts[1].strip()
                        else:
                            obs_part = full_content.split("：", 1)[-1].strip() if "：" in full_content else full_content

                        # 提取漲跌
                        change_match = re.search(r'\(([+-]?[\d\.]+)\%\)', rec_part)
                        change = float(change_match.group(1)) if change_match else 0
                        
                        new_data.append({
                            "日期": current_date,
                            "標的": target_clean,
                            "操作": "買進" if "✅" in header or "買" in header else "觀察",
                            "漲跌%": change,
                            "盤前觀察": obs_part,
                            "盤後紀錄": rec_part
                        })

                if new_data:
                    new_df = pd.DataFrame(new_data)
                    existing_df = conn.read()
                    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
                    conn.update(data=updated_df)
                    st.success(f"🎊 已精準同步 {len(new_data)} 筆紀錄！")
                    st.rerun()
            except Exception as e:
                st.error(f"解析出錯：{str(e)}")

# --- 主畫面：視覺化戰情室 ---
try:
    df = conn.read().dropna(subset=['標的'])
    df['漲跌%'] = pd.to_numeric(df['漲跌%'], errors='coerce').fillna(0)
    
    # 1. 頂部勝率指標
    win_rate = (len(df[df['漲跌%'] > 0]) / len(df) * 100) if len(df) > 0 else 0
    st.metric("📊 歷史預判總勝率", f"{win_rate:.1f}%")

    # 2. 勝率圓餅圖
    df['類別'] = df['漲跌%'].apply(lambda x: '獲利' if x > 0 else ('虧損' if x < 0 else '持平'))
    fig = px.pie(df, names='類別', hole=0.4, color='類別', 
                 color_discrete_map={'獲利':'#ef5350', '虧損':'#26a69a', '持平':'#bdbdbd'})
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # 3. 標的追蹤清單
    st.subheader("🔍 個股追蹤歷程")
    unique_targets = sorted(df['標的'].unique())
    for target in unique_targets:
        t_df = df[df['標的'] == target].sort_values(by='日期', ascending=False)
        l_change = t_df.iloc[0]['漲跌%']
        color = "#ef5350" if l_change > 0 else ("#26a69a" if l_change < 0 else "#bdbdbd")
        
        with st.expander(f"📌 {target} (歷次平均：{t_df['漲跌%'].mean():.1f}%)"):
            for _, row in t_df.iterrows():
                st.markdown(f"""
                <div style="border-left:5px solid {color}; padding:15px; background:#f8f9fa; border-radius:10px; margin-bottom:10px;">
                    <span style="color:gray;">📅 日期：{row['日期']}</span> | <strong>動作：{row['操作']}</strong> | <span style="color:{color}; font-weight:bold;">結果：{row['漲跌%']}%</span><br>
                    <div style="margin-top:10px;">
                        <p style="margin-bottom:5px;">🔍 <b>盤前觀察：</b><br>{row['盤前觀察']}</p>
                        <p style="margin-bottom:0px;">📝 <b>盤後紀錄：</b><br>{row['盤後紀錄']}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
except:
    st.info("請貼上資料進行精密解析。")
