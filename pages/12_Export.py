from __future__ import annotations

import pandas as pd
import streamlit as st

from src.accounting_rules import compute_adjusted_tb
from src.audit_tests import build_supplementary_audit_sheets, run_revenue_and_expense_review
from src.auditor_report import build_draft_auditor_report, collect_unresolved_issues
from src.cashflow import build_cash_flow_statement
from src.exporters import build_accounting_audit_workbook
from src.financial_statements import build_financial_statements
from src.mapping import detect_mapping_conflicts_and_unmapped
from src.notes import build_notes_and_checklist
from src.risk_scoring import build_account_risk_register_and_workpaper
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="12 Export Excel Pack", page_icon="📦", layout="wide")
setup = render_sidebar_and_header("export", "12. ส่งออก Excel Accounting & Audit Pack (Formula-Driven)", "12. Export Complete Excel Pack")
lang = setup.language

tb_df = st.session_state["tb_normalized"]
gl_df = st.session_state["gl_normalized"]
mapping_df = st.session_state["coa_mapping"]

if tb_df.empty:
    st.info("กรุณานำเข้าข้อมูล Trial Balance ก่อนส่งออก Excel Pack")
    render_page_review_signoff("export", lang)
    st.stop()

if st.button("⚙️ สร้างไฟล์ Excel Pack พร้อมสูตรและตรวจสอบ Formula_Check", type="primary", use_container_width=True):
    with st.spinner("กำลังสร้าง Workbook 50+ Sheets พร้อมสูตร Excel จริง และตรวจสอบ Formula Integrity..."):
        adjusted_tb = compute_adjusted_tb(tb_df, st.session_state["adjustments"], mapping_df)
        unmapped_df, _ = detect_mapping_conflicts_and_unmapped(mapping_df, tb_df)
        fs_res = build_financial_statements(adjusted_tb, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"])
        cf_res = build_cash_flow_statement(adjusted_tb, gl_df, fs_res, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"])

        notes_idx = st.session_state["notes_index"]
        notes_drf = st.session_state["notes_draft"]
        if notes_idx.empty or notes_drf.empty:
            notes_idx, notes_drf = build_notes_and_checklist(adjusted_tb, setup)

        rev_df, exp_df = run_revenue_and_expense_review(adjusted_tb, gl_df, mapping_df, setup)
        risk_reg_df, wp_df = build_account_risk_register_and_workpaper(adjusted_tb, gl_df, mapping_df, setup, st.session_state["risk_weights"])
        supp = build_supplementary_audit_sheets(adjusted_tb, gl_df, mapping_df, setup)
        unresolved = collect_unresolved_issues(st.session_state["dq_report"], unmapped_df, st.session_state["adjustments"], fs_res, notes_idx)
        aud_draft_df, aud_ref_df = build_draft_auditor_report(
            setup,
            unresolved,
            selected_opinion=st.session_state["auditor_opinion"],
            cpa_custom_edits=st.session_state["auditor_edits"],
        )

        xlsx_bytes, fname, formula_chk_df = build_accounting_audit_workbook(
            setup=setup,
            tb_df=tb_df,
            gl_df=gl_df,
            dq_df=st.session_state["dq_report"],
            mapping_df=mapping_df,
            unmapped_df=unmapped_df,
            adjustments_df=st.session_state["adjustments"],
            adjusted_tb=adjusted_tb,
            prior_extracted_df=st.session_state["prior_year_extracted"],
            prior_review_df=st.session_state["prior_year_review"],
            fs_result=fs_res,
            cf_result=cf_res,
            notes_index_df=notes_idx,
            notes_draft_df=notes_drf,
            rev_review_df=rev_df,
            exp_review_df=exp_df,
            risk_reg_df=risk_reg_df,
            workpaper_df=wp_df,
            supp_audit=supp,
            auditor_draft_df=aud_draft_df,
            auditor_ref_df=aud_ref_df,
            change_log=st.session_state["change_log"],
            grouping_version=st.session_state["grouping_version"],
        )
        st.session_state["last_export_bytes"] = xlsx_bytes
        st.session_state["last_export_name"] = fname
        st.session_state["last_formula_check"] = formula_chk_df
        log_change("Export", "Generate Excel Pack", fname, new_value=f"{len(formula_chk_df)} formula-checked sheets")

if "last_export_bytes" in st.session_state:
    fname = st.session_state["last_export_name"]
    fchk = st.session_state["last_formula_check"]
    err_f = int((fchk["Status"] == "Error").sum()) if not fchk.empty else 0
    if err_f == 0:
        st.success(f"✅ สร้างไฟล์ `{fname}` สำเร็จ! ไม่พบ Formula Error (`#REF!`, `#NAME?`, ฯลฯ)")
    else:
        st.error(f"⚠️ พบประเด็นใน Formula Check จำนวน {err_f} รายการ กรุณาตรวจสอบตารางด้านล่าง")

    st.download_button(
        f"⬇️ ดาวน์โหลด {fname}",
        data=st.session_state["last_export_bytes"],
        file_name=fname,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )

    st.subheader("ผลตรวจสอบ Formula Integrity (Formula_Check)")
    st.dataframe(fchk, use_container_width=True, hide_index=True)

render_page_review_signoff("export", lang)
