from __future__ import annotations

import pandas as pd
import streamlit as st

from src.accounting_rules import generate_proposed_adjustments
from src.loaders import (
    GL_COLUMN_SYNONYMS,
    TB_COLUMN_SYNONYMS,
    auto_detect_columns,
    generate_gl_template_bytes,
    generate_tb_template_bytes,
    list_excel_sheets,
    normalize_gl,
    normalize_tb,
    read_excel_sheet_raw,
)
from src.mapping import build_initial_coa_mapping
from src.models import t
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header
from src.validators import run_data_quality_checks


st.set_page_config(page_title="01 นำเข้าข้อมูล TB & GL", page_icon="📥", layout="wide")
setup = render_sidebar_and_header("import", "01. นำเข้าข้อมูล Trial Balance (TB) และ General Ledger (GL)", "01. Import Trial Balance & General Ledger")
lang = setup.language

if not setup.framework_confirmed:
    st.warning("⚠️ กรุณาไปที่หน้า `00_Entity_and_Framework_Setup` เพื่อยืนยันกรอบมาตรฐานบัญชีก่อนสรุปงบการเงิน (สามารถนำเข้าไฟล์เพื่อตรวจสอบเบื้องต้นได้)")

# Template downloads
t1, t2 = st.columns(2)
with t1:
    st.download_button(
        "⬇️ ดาวน์โหลดตัวอย่าง Template TB (.xlsx)",
        data=generate_tb_template_bytes(),
        file_name="template_trial_balance.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
with t2:
    st.download_button(
        "⬇️ ดาวน์โหลดตัวอย่าง Template GL (.xlsx)",
        data=generate_gl_template_bytes(),
        file_name="template_general_ledger.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.divider()
col_tb, col_gl = st.columns(2)

# --- TB UPLOAD ---
with col_tb:
    st.subheader("1) นำเข้า Trial Balance (TB)")
    tb_file = st.file_uploader("อัปโหลดไฟล์ Excel (.xlsx) สำหรับ TB", type=["xlsx"], key="tb_uploader")
    if tb_file is not None:
        tb_bytes = tb_file.read()
        tb_sheets = list_excel_sheets(tb_bytes)
        tb_sheet = st.selectbox("เลือก Sheet ของ TB", options=tb_sheets, key="tb_sheet_sel")
        tb_hdr = st.number_input("แถวหัวตาราง (Header Row, 1-based)", min_value=1, max_value=30, value=1, key="tb_hdr_row")
        raw_tb = read_excel_sheet_raw(tb_bytes, tb_sheet, header_row=int(tb_hdr) - 1)
        st.caption(f"พบ {len(raw_tb)} แถว | คอลัมน์: {', '.join(raw_tb.columns[:8])}")
        cols_opt = ["(ไม่ใช้)"] + list(raw_tb.columns)
        det_tb = auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS)

        def idx_of(col_name: str | None) -> int:
            return cols_opt.index(col_name) if col_name in cols_opt else 0

        with st.expander("กำหนดการจับคู่คอลัมน์ TB (Column Mapping)", expanded=True):
            tb_map = {
                "account_code": st.selectbox("Account Code / รหัสบัญชี *", cols_opt, index=idx_of(det_tb["account_code"]), key="tb_c_code"),
                "account_name": st.selectbox("Account Name / ชื่อบัญชี *", cols_opt, index=idx_of(det_tb["account_name"]), key="tb_c_name"),
                "opening_balance": st.selectbox("Opening Balance / ยอดยกมา", cols_opt, index=idx_of(det_tb["opening_balance"]), key="tb_c_open"),
                "debit": st.selectbox("Debit / เดบิต", cols_opt, index=idx_of(det_tb["debit"]), key="tb_c_dr"),
                "credit": st.selectbox("Credit / เครดิต", cols_opt, index=idx_of(det_tb["credit"]), key="tb_c_cr"),
                "balance": st.selectbox("Balance / ยอดคงเหลือ", cols_opt, index=idx_of(det_tb["balance"]), key="tb_c_bal"),
                "prior_balance": st.selectbox("Prior Balance / ยอดปีก่อน", cols_opt, index=idx_of(det_tb["prior_balance"]), key="tb_c_py"),
                "department": st.selectbox("Department / แผนก", cols_opt, index=idx_of(det_tb["department"]), key="tb_c_dept"),
            }
            tb_map = {k: (None if v == "(ไม่ใช้)" else v) for k, v in tb_map.items()}

        if st.button("✅ นำเข้าและ Normalize TB", type="primary", use_container_width=True):
            norm_tb, errs = normalize_tb(raw_tb, tb_map, tb_file.name, tb_sheet, int(tb_hdr))
            if errs:
                for e in errs:
                    st.error(e)
            else:
                st.session_state["tb_raw_name"] = tb_file.name
                st.session_state["tb_raw_sheet"] = tb_sheet
                st.session_state["tb_normalized"] = norm_tb
                gl_curr = st.session_state["gl_normalized"]
                dq_df, dq_det = run_data_quality_checks(norm_tb, gl_curr, setup.period_start, setup.period_end)
                st.session_state["dq_report"] = dq_df
                st.session_state["dq_details"] = dq_det
                coa = build_initial_coa_mapping(norm_tb, gl_curr, setup.materiality_amount, st.session_state["coa_mapping"])
                st.session_state["coa_mapping"] = coa
                if st.session_state["adjustments"].empty:
                    st.session_state["adjustments"] = generate_proposed_adjustments(norm_tb, gl_curr, coa, setup.period_end)
                log_change("Import", "Import TB", f"{tb_file.name}:{tb_sheet}", new_value=f"{len(norm_tb)} rows")
                st.success(f"นำเข้า TB สำเร็จ {len(norm_tb)} บัญชี!")
                st.rerun()

# --- GL UPLOAD ---
with col_gl:
    st.subheader("2) นำเข้า General Ledger (GL)")
    gl_file = st.file_uploader("อัปโหลดไฟล์ Excel (.xlsx) สำหรับ GL", type=["xlsx"], key="gl_uploader")
    if gl_file is not None:
        gl_bytes = gl_file.read()
        gl_sheets = list_excel_sheets(gl_bytes)
        gl_sheet = st.selectbox("เลือก Sheet ของ GL", options=gl_sheets, key="gl_sheet_sel")
        gl_hdr = st.number_input("แถวหัวตาราง (Header Row, 1-based)", min_value=1, max_value=30, value=1, key="gl_hdr_row")
        raw_gl = read_excel_sheet_raw(gl_bytes, gl_sheet, header_row=int(gl_hdr) - 1)
        st.caption(f"พบ {len(raw_gl)} แถว | คอลัมน์: {', '.join(raw_gl.columns[:8])}")
        g_opts = ["(ไม่ใช้)"] + list(raw_gl.columns)
        det_gl = auto_detect_columns(list(raw_gl.columns), GL_COLUMN_SYNONYMS)

        def gidx(col_name: str | None) -> int:
            return g_opts.index(col_name) if col_name in g_opts else 0

        with st.expander("กำหนดการจับคู่คอลัมน์ GL (รองรับทั้ง Dr/Cr และ Debit Account/Credit Account)", expanded=True):
            gl_map = {
                "date": st.selectbox("Date / วันที่ *", g_opts, index=gidx(det_gl["date"]), key="gl_c_date"),
                "doc_no": st.selectbox("Document No / เลขที่เอกสาร *", g_opts, index=gidx(det_gl["doc_no"]), key="gl_c_doc"),
                "account_code": st.selectbox("Account Code / รหัสบัญชี", g_opts, index=gidx(det_gl["account_code"]), key="gl_c_code"),
                "account_name": st.selectbox("Account Name / ชื่อบัญชี", g_opts, index=gidx(det_gl["account_name"]), key="gl_c_name"),
                "debit": st.selectbox("Debit / เดบิต", g_opts, index=gidx(det_gl["debit"]), key="gl_c_dr"),
                "credit": st.selectbox("Credit / เครดิต", g_opts, index=gidx(det_gl["credit"]), key="gl_c_cr"),
                "debit_account": st.selectbox("Debit Account (กรณีแถวคู่)", g_opts, index=gidx(det_gl["debit_account"]), key="gl_c_dra"),
                "credit_account": st.selectbox("Credit Account (กรณีแถวคู่)", g_opts, index=gidx(det_gl["credit_account"]), key="gl_c_cra"),
                "amount": st.selectbox("Amount (กรณีไม่มี Dr/Cr แยก)", g_opts, index=gidx(det_gl["amount"]), key="gl_c_amt"),
                "description": st.selectbox("Description / รายละเอียด", g_opts, index=gidx(det_gl["description"]), key="gl_c_desc"),
                "reference": st.selectbox("Reference / อ้างอิง", g_opts, index=gidx(det_gl["reference"]), key="gl_c_ref"),
                "cost_center": st.selectbox("Cost Center", g_opts, index=gidx(det_gl["cost_center"]), key="gl_c_cc"),
                "department": st.selectbox("Department / แผนก", g_opts, index=gidx(det_gl["department"]), key="gl_c_dept"),
                "currency": st.selectbox("Currency / สกุลเงิน", g_opts, index=gidx(det_gl["currency"]), key="gl_c_curr"),
                "entry_type": st.selectbox("Entry Type / ประเภท", g_opts, index=gidx(det_gl["entry_type"]), key="gl_c_type"),
                "posted_by": st.selectbox("Posted By / ผู้บันทึก", g_opts, index=gidx(det_gl["posted_by"]), key="gl_c_user"),
            }
            gl_map = {k: (None if v == "(ไม่ใช้)" else v) for k, v in gl_map.items()}

        if st.button("✅ นำเข้าและ Normalize GL", type="primary", use_container_width=True):
            norm_gl, errs = normalize_gl(raw_gl, gl_map, gl_file.name, gl_sheet, int(gl_hdr))
            if errs:
                for e in errs:
                    st.error(e)
            else:
                st.session_state["gl_raw_name"] = gl_file.name
                st.session_state["gl_raw_sheet"] = gl_sheet
                st.session_state["gl_normalized"] = norm_gl
                tb_curr = st.session_state["tb_normalized"]
                dq_df, dq_det = run_data_quality_checks(tb_curr, norm_gl, setup.period_start, setup.period_end)
                st.session_state["dq_report"] = dq_df
                st.session_state["dq_details"] = dq_det
                if not tb_curr.empty:
                    coa = build_initial_coa_mapping(tb_curr, norm_gl, setup.materiality_amount, st.session_state["coa_mapping"])
                    st.session_state["coa_mapping"] = coa
                log_change("Import", "Import GL", f"{gl_file.name}:{gl_sheet}", new_value=f"{len(norm_gl)} rows")
                st.success(f"นำเข้า GL สำเร็จ {len(norm_gl)} แถว!")
                st.rerun()

st.divider()
st.subheader("ตัวอย่างข้อมูลที่ Normalize แล้วพร้อม Source Traceability")
tab_tb, tab_gl = st.tabs(["TB_Normalized", "GL_Normalized"])
with tab_tb:
    tb_df = st.session_state["tb_normalized"]
    if not tb_df.empty:
        st.dataframe(tb_df, use_container_width=True, hide_index=True)
        st.download_button("⬇️ ดาวน์โหลด TB_Normalized (.csv)", tb_df.to_csv(index=False).encode("utf-8-sig"), "TB_Normalized.csv", "text/csv")
    else:
        st.info("ยังไม่มีข้อมูล TB")
with tab_gl:
    gl_df = st.session_state["gl_normalized"]
    if not gl_df.empty:
        st.dataframe(gl_df.head(500), use_container_width=True, hide_index=True)
        st.download_button("⬇️ ดาวน์โหลด GL_Normalized (.csv)", gl_df.to_csv(index=False).encode("utf-8-sig"), "GL_Normalized.csv", "text/csv")
    else:
        st.info("ยังไม่มีข้อมูล GL")

render_page_review_signoff("import", lang)
