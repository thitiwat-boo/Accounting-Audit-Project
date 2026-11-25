from __future__ import annotations

import streamlit as st

from src.accounting_rules import compute_adjusted_tb
from src.audit_tests import build_supplementary_audit_sheets, run_revenue_and_expense_review
from src.risk_scoring import build_account_risk_register_and_workpaper
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="08 Audit Workpaper", page_icon="🛡️", layout="wide")
setup = render_sidebar_and_header("audit", "08. Audit Workpaper, Risk Scoring และสอบทานรายได้-ค่าใช้จ่าย", "08. Audit Workpaper & Risk Scoring")
lang = setup.language

tb_df = st.session_state["tb_normalized"]
gl_df = st.session_state["gl_normalized"]
mapping_df = st.session_state["coa_mapping"]

if tb_df.empty:
    st.info("กรุณานำเข้าข้อมูล TB/GL ก่อน")
    render_page_review_signoff("audit", lang)
    st.stop()

adjusted_tb = compute_adjusted_tb(tb_df, st.session_state["adjustments"], mapping_df)

with st.expander("⚖️ ปรับน้ำหนัก Risk Scoring Weights (ปรับแต่งได้ตามความเสี่ยงกิจการ)"):
    rw = dict(st.session_state["risk_weights"])
    c1, c2, c3, c4 = st.columns(4)
    rw["materiality_ratio"] = c1.number_input("Materiality Weight", 0, 50, int(rw["materiality_ratio"]))
    rw["period_fluctuation"] = c2.number_input("Fluctuation Weight", 0, 50, int(rw["period_fluctuation"]))
    rw["management_override_or_manual"] = c3.number_input("Manual / Override Weight", 0, 50, int(rw["management_override_or_manual"]))
    rw["year_end_cutoff"] = c4.number_input("Year-end Cut-off Weight", 0, 50, int(rw["year_end_cutoff"]))
    c5, c6, c7 = st.columns(3)
    rw["related_party"] = c5.number_input("Related Party Weight", 0, 50, int(rw["related_party"]))
    rw["accounting_complexity_or_estimate"] = c6.number_input("Estimate / Complexity Weight", 0, 50, int(rw["accounting_complexity_or_estimate"]))
    rw["evidence_gap_or_suspense"] = c7.number_input("Evidence Gap / Suspense Weight", 0, 50, int(rw["evidence_gap_or_suspense"]))
    if st.button("บันทึกน้ำหนักความเสี่ยง"):
        st.session_state["risk_weights"] = rw
        log_change("Audit Risk", "Update Weights", "Risk Weights", new_value=str(rw))
        st.success("อัปเดตน้ำหนักความเสี่ยงแล้ว")

risk_reg_df, wp_df = build_account_risk_register_and_workpaper(
    adjusted_tb, gl_df, mapping_df, setup, st.session_state["risk_weights"]
)
rev_df, exp_df = run_revenue_and_expense_review(adjusted_tb, gl_df, mapping_df, setup)
supp = build_supplementary_audit_sheets(adjusted_tb, gl_df, mapping_df, setup)

st.info("ข้อกำหนด: ข้อบ่งชี้ความเสี่ยงทั้งหมดเป็น `Suggested Audit Procedure` จากรูปแบบข้อมูล เพื่อช่วยจัดลำดับความสำคัญในการสอบทาน ไม่ใช่คำรับรองว่ามีการทุจริต")

tabs = st.tabs([
    f"Audit Risk Register ({len(risk_reg_df)})",
    f"Audit Workpaper ({len(wp_df)})",
    f"Revenue Review ({len(rev_df)})",
    f"Expense Review ({len(exp_df)})",
    "Confirmation List",
    "Subsequent Events",
    "Related Party & Tax",
])

with tabs[0]:
    st.dataframe(risk_reg_df.sort_values("Risk_Score", ascending=False), use_container_width=True, hide_index=True)
    st.download_button("⬇️ ดาวน์โหลด Audit_Risk_Register (.csv)", risk_reg_df.to_csv(index=False).encode("utf-8-sig"), "Audit_Risk_Register.csv", "text/csv")

with tabs[1]:
    st.dataframe(wp_df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ ดาวน์โหลด Audit_Workpaper (.csv)", wp_df.to_csv(index=False).encode("utf-8-sig"), "Audit_Workpaper.csv", "text/csv")

with tabs[2]:
    st.dataframe(rev_df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ ดาวน์โหลด Revenue_Review (.csv)", rev_df.to_csv(index=False).encode("utf-8-sig"), "Revenue_Review.csv", "text/csv")

with tabs[3]:
    st.dataframe(exp_df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ ดาวน์โหลด Expense_Review (.csv)", exp_df.to_csv(index=False).encode("utf-8-sig"), "Expense_Review.csv", "text/csv")

with tabs[4]:
    st.dataframe(supp["Confirmation_Request_List"], use_container_width=True, hide_index=True)

with tabs[5]:
    st.dataframe(supp["Subsequent_Events"], use_container_width=True, hide_index=True)

with tabs[6]:
    st.subheader("Related Party Check")
    st.dataframe(supp["Related_Party_Check"], use_container_width=True, hide_index=True)
    st.subheader("Tax Check (VAT / WHT / CIT)")
    st.dataframe(supp["Tax_Check"], use_container_width=True, hide_index=True)

render_page_review_signoff("audit", lang)
