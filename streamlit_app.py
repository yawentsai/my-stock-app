import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

st.set_page_config(page_title="交易戰情室 3.1", layout="wide")
st.title("🎯 交易戰情室 3.1 (強效淨化版)")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 側邊欄 ---
with st.sidebar:
    st.header("📥 批次同步筆記")
    user_input = st.text_area("在此貼上整理好的筆記：", height=400)
    
    if st.button("🚀 開始精密解析"):
        if user_input:
            try:
                new_data = []
                fallback_date = datetime.now().strftime("%m/%d")

                date_blocks = re.split(r'\n(?=\d{1,2}/\d{1,2})', '\n' + user_input.strip())
                for d_block in date_blocks:
                    d_block = d_block.strip()
                    if not d_block: continue
                    
                    lines = d_block.split('\n')
                    date_match = re.match(r'(\d{1,2}/\d{1,2})', lines[0].strip())
                    if date_match:
                        current_date = date_match.group(1)
                        content_to_parse = '\n'.join(lines[1:])
                    else:
                        current_date = fallback_date
                        content_to_parse = d_block

                    target_blocks = re.split(r'\n(?=✅|[\u4e00-\u9fa5]{2,5}[:：])', '\n' + content_to_parse)
                    for t_block in target_blocks:
                        t_block = t_block.strip()
                        if not t_block: continue

                        t_lines = t_block.split('\n')
                        header = t_lines[0]

                        if "：" in header or ":" in header:
                            target_raw = re.split(r'[：:]', header)[0].replace('✅', '').strip()
                            target_clean = re.sub(r'\d+', '', target_raw).strip()
                            if len(target_clean) > 8 or not target_clean: continue
                            
                            full_content = "\n".join(t_lines)
                            obs_part, rec_part = "", ""
                            
                            if "👉" in full_content:
                                parts = re.split(r'👉[🏻]?', full_content)
                                obs_part = parts[0].split("：", 1)[-1].strip() if "：" in parts[0] else parts[0]
                                rec_part = parts[1].strip()
                            else:
                                obs_part = full_content.split("：", 1)[-1].strip() if "：" in full_content else full_content

                            change_match = re.search(r'\(([+-]?[\d\.]+)\%\)', rec_part if rec_part else full_content)
                            change = float(change_match.group(1)) if change_match else 0
                            
                            is_buy = "✅" in header or "買" in full_content
                            
                            new_data.append({
                                "日期": current_date,
                                "標的": target_clean,
                                "操作": "買進" if is_buy else "觀察",
                                "漲跌%": change,
                                "盤前觀察": obs_part,
                                "盤後紀錄": rec_part
                            })

                if new_data:
                    new_df = pd.DataFrame(new_data)
                    existing_df = conn.read(ttl=0)
                    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
                    conn.update(data=updated_df)
                    st.cache_data.clear()
                    st.success(f"🎊 成功同步 {len(new_data)} 筆資料！")
                    st.rerun()
                else:
                    st.warning("沒抓到資料，請檢查格式。")
            except Exception as e:
                st.error(f"解析錯誤：{str(e)}")

# --- 主畫面顯示 ---
try:
    df = conn.read(ttl=0).dropna(subset=['標的'])
    
    # 【關鍵強效淨化區】：無論試算表多亂，在顯示前強制清洗
    df['標的'] = df['標的'].astype(str)
    # 1. 強制剃除所有數字，解決「國巨2327」的問題
    df['標的'] = df['標的'].str.replace(r'\d+', '', regex=True).str.strip()
    # 2. 強制過濾掉異常長度的句子，字數大於 6 的直接隱藏
    df = df[df['標的'].str.len() <= 6]
    df = df[df['標的'].str.len() > 0]
    
    df['漲跌%'] = pd.to_numeric(df['漲跌%'], errors='coerce').fillna(0)
    
    if not df.empty:
        win_rate = (len(df[df['漲跌%'] > 0]) / len(df) * 100)
        st.metric("📊 歷史預判總勝率", f"{win_rate:.1f}%")
        
        df['類別'] = df['漲跌%'].apply(lambda x: '獲利' if x > 0 else ('虧損' if x < 0 else '持平'))
        fig = px.pie(df, names='類別', hole=0.4, color='類別', 
                     color_discrete_map={'獲利':'#ef5350', '虧損':'#26a69a', '持平':'#bdbdbd'})
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        tab1, tab2 = st.tabs(["🗂️ 依【個股】深度追蹤", "📅 依【日期】盤後日誌"])

        with tab1:
            st.subheader("🔍 個股深度追蹤歷程")
            for target in sorted(df['標的'].unique()):
                t_df = df[df['標的'] == target].sort_values(by='日期', ascending=False)
                with st.expander(f"📌 {target} (總紀錄：{len(t_df)} 筆)"):
                    for _, row in t_df.iterrows():
                        color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "#bdbdbd")
                        st.markdown(f"""
                        <div style="border-left:5px solid {color}; padding:10px; background:#f8f9fa; margin-bottom:10px;">
                            <b>{row['日期']} | {row['操作']} | {row['漲跌%']}%</b><br>
                            <div style="margin-top:6px; font-size:0.95rem;">
                                <span style="color:#555;">🔍 <b>盤前：</b> {row['盤前觀察']}</span><br>
                                <span style="color:#222;">📝 <b>盤後：</b> {row['盤後紀錄']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

        with tab2:
            st.subheader("📝 每日操作與資金流向總覽")
            for date in sorted(df['日期'].unique(), reverse=True):
                d_df = df[df['日期'] == date]
                buy_count = len(d_df[d_df['操作'] == '買進'])
                obs_count = len(d_df[d_df['操作'] == '觀察'])
                
                with st.expander(f"📅 {date} (買進: {buy_count} 檔 | 觀察: {obs_count} 檔)", expanded=True if date == df['日期'].max() else False):
                    for _, row in d_df.iterrows():
                        action_badge = f"<span style='background-color:#ef5350; color:white; padding:2px 6px; border-radius:4px; font-size:0.8rem;'>買進</span>" if row['操作'] == '買進' else f"<span style='background-color:#bdbdbd; color:white; padding:2px 6px; border-radius:4px; font-size:0.8rem;'>觀察</span>"
                        result_color = "#ef5350" if row['漲跌%'] > 0 else ("#26a69a" if row['漲跌%'] < 0 else "gray")
                        
                        st.markdown(f"""
                        <div style="padding:8px; border-bottom:1px solid #eee;">
                            {action_badge} <strong>{row['標的']}</strong> 
                            <span style="color:{result_color}; float:right; font-weight:bold;">{row['漲跌%']}%</span><br>
                            <span style="color:#666; font-size:0.85rem;">📝 {row['盤後紀錄']}</span>
                        </div>
                        """, unsafe_allow_html=True)

    else:
        st.info("資料庫目前為空，請在左側貼上資料進行解析。")
except Exception as e:
    st.info("系統連線中，或資料格式需要重整。")
