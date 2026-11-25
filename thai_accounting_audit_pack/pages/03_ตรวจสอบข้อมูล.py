from __future__ import annotations

import streamlit as st

from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header
from src.validators import run_data_quality_checks


st.set_page_config(page_title="03 ตรวจสอบข้อมูล Data Quality", page_icon="🔍", layout="wide")
setup = render_sidebar_and_header("dq", "03. ตรวจสอบคุณภาพข้อมูล (Data Quality Report)", "03. Data Quality & Validation")
lang = setup.language

tb_df = st.session_state["tb_normalized"]
gl_df = st.session_state["gl_normalized"]

if st.button("🔄 ประมวลผล Data Quality Checks ใหม่", type="primary"):
    dq_df, dq_det = run_data_quality_checks(tb_df, gl_df, setup.period_start, setup.period_end)
    st.session_state["dq_report"] = dq_df
    st.session_state["dq_details"] = dq_det
    log_change("Data Quality", "Re-run Checks", "All 14 checks")
    st.rerun()

dq_df = st.session_state["dq_report"]
dq_det = st.session_state["dq_details"]

if dq_df.empty:
    st.info("กรุณานำเข้าข้อมูล TB/GL ในหน้า `01_นำเข้าข้อมูล` หรือโหลด Sample Data จากหน้าหลักก่อน")
else:
    p_cnt = int((dq_df["Status"] == "Pass").sum())
    w_cnt = int((dq_df["Status"] == "Warning").sum())
    e_cnt = int((dq_df["Status"] == "Error").sum())
    c1, c2, c3 = st.columns(3)
    c1.success(f"✅ Pass: {p_cnt}")
    c2.warning(f"⚠️ Warning: {w_cnt}")
    c3.error(f"❌ Error: {e_cnt}")

    st.dataframe(dq_df, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ ดาวน์โหลด Data Quality Report (.csv)",
        dq_df.to_csv(index=False).encode("utf-8-sig"),
        "Data_Quality_Report.csv",
        "text/csv",
    )

    if dq_det:
        st.subheader("🔎 ดูแถวต้นทางของรายการที่พบประเด็น (Show Source Rows)")
        sel_id = st.selectbox("เลือก Check ID เพื่อดูรายละเอียด", options=list(dq_det.keys()))
        if sel_id in dq_det:
            st.dataframe(dq_det[sel_id], use_container_width=True, hide_index=True)

render_page_review_signoff("dq", lang)
