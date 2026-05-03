import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

st.set_page_config(page_title="個人交易紀錄App", layout="centered")

# 建立與 Google Sheets 的連線
conn = st.connection("gsheets", type=GSheetsConnection)

def parse_data(txt):
    days = re.split(r'(\d+/\d+.*?)：?', txt)
    data = []
    curr_date = None
    for p in days:
        p = p.strip()
        if not p: continue
        d_match = re.match(r'(\d+/\d+)', p)
        if d_match:
            curr_date = d_match.group(1)
            continue
        if curr_date:
            blocks = re.split(r'\n\n', p)
            for b in blocks:
                ls = b.strip().split('\n')
                if not ls or '————' in ls[0]: continue
                header = ls[0]
                is_buy = '✅' in header
                name = header.replace('✅', '').split('：')[0].strip()
                pct = 0.0
                note = ""
                for l in ls:
                    if '👉🏻' in l:
                        note = l
                        m = re.search(r'([+-]?\d+\.?\d*)%', l)
                        if m: pct = float(m.group(1))
                        if '漲停' in l: pct = 10.0
                data.append({"日期": curr_date, "標的": name, "操作": "買進" if is_buy else "觀察", "漲跌%": pct, "盤後紀錄": note})
    return pd.DataFrame(data)

st.title("📊 交易紀錄自動化系統")

txt_input = st.text_area("請在此貼上你的盤後筆記：", height=250)

if st.button("🚀 解析並同步到試算表"):
    if txt_input:
        new_df = parse_data(txt_input)
        try:
            old_df = conn.read()
            final_df = pd.concat([old_df, new_df], ignore_index=True)
            conn.update(data=final_df)
            st.success("🎉 資料已成功同步至 Google 試算表！")
            st.table(new_df)
        except Exception as e:
            st.error(f"連線異常，請檢查 Secrets 設定。{e}")

if st.checkbox("查看歷史庫存紀錄"):
    st.dataframe(conn.read())
