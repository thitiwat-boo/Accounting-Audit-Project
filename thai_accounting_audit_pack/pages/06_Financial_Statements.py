from __future__ import annotations

import pandas as pd
import streamlit as st

from src.accounting_rules import compute_adjusted_tb
from src.cashflow import build_cash_flow_statement
from src.financial_statements import build_financial_statements
from src.ui_helpers import render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="06 Financial Statements", page_icon="📄", layout="wide")
setup = render_sidebar_and_header("fs", "06. งบการเงินฉบับร่าง (Financial Statements & Detail Schedules)", "06. Draft Financial Statements")
lang = setup.language

tb_df = st.session_state["tb_normalized"]
gl_df = st.session_state["gl_normalized"]
mapping_df = st.session_state["coa_mapping"]

if tb_df.empty:
    st.info("กรุณานำเข้าข้อมูล Trial Balance และทำ Mapping ก่อน")
    render_page_review_signoff("fs", lang)
    st.stop()

adjusted_tb = compute_adjusted_tb(tb_df, st.session_state["adjustments"], mapping_df)
fs_res = build_financial_statements(
    adjusted_tb, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"]
)
cf_res = build_cash_flow_statement(
    adjusted_tb, gl_df, fs_res, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"]
)

for w in fs_res.get("warnings", []):
    st.warning(f"⚠️ {w}")

c_opt1, c_opt2 = st.columns(2)
show_formula = c_opt1.toggle("📐 Show Formula (แสดงสูตร Excel ของทุกบรรทัด)", value=False)
show_source = c_opt2.toggle("🔎 Show Source (แสดงชีท/บัญชีต้นทางของทุกบรรทัด)", value=False)

def _filter_fs_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["Section", "Line_Item", "Note", "Current_Year", "Prior_Year", "Row_Type"]
    if show_formula and "Formula_Preview" in df.columns:
        cols.append("Formula_Preview")
    if show_source and "Source_Ref" in df.columns:
        cols.append("Source_Ref")
    return df[[c for c in cols if c in df.columns]]

t_bs, t_is, t_sce, t_cf, t_det = st.tabs([
    "1. งบแสดงฐานะการเงิน",
    "2. งบกำไรขาดทุน",
    "3. งบเปลี่ยนแปลงส่วนของเจ้าของ",
    "4. งบกระแสเงินสด",
    "5. Detail Schedules (D_*)",
])

with t_bs:
    st.subheader(f"งบแสดงฐานะการเงิน (ฉบับร่าง) ณ วันที่ {setup.period_end} — หน่วย: {setup.unit_scale}")
    st.caption(f"รูปแบบ: {setup.dbd_template} | กรอบ: {setup.framework}")
    bs_df = fs_res["balance_sheet"]
    st.dataframe(_filter_fs_cols(bs_df), use_container_width=True, hide_index=True)
    diff = fs_res["reconciliations"]["bs_balance_diff"]
    if abs(diff) < 0.01:
        st.success("✅ สมการบัญชีสมดุล: สินทรัพย์ = หนี้สิน + ส่วนของเจ้าของ (ผลต่าง = 0.00)")
    else:
        st.error(f"❌ สมการบัญชียังไม่สมดุล: ผลต่าง = {diff:,.2f}")
    st.download_button("⬇️ ดาวน์โหลด งบแสดงฐานะการเงิน (.csv)", bs_df.to_csv(index=False).encode("utf-8-sig"), "FS_Balance_Sheet.csv", "text/csv")

with t_is:
    st.subheader(f"งบกำไรขาดทุน (ฉบับร่าง) สำหรับงวดสิ้นสุด {setup.period_end} — หน่วย: {setup.unit_scale}")
    is_df = fs_res["income_statement"]
    st.dataframe(_filter_fs_cols(is_df), use_container_width=True, hide_index=True)
    st.download_button("⬇️ ดาวน์โหลด งบกำไรขาดทุน (.csv)", is_df.to_csv(index=False).encode("utf-8-sig"), "FS_Income_Statement.csv", "text/csv")

with t_sce:
    st.subheader("งบแสดงการเปลี่ยนแปลงส่วนของผู้ถือหุ้น / เจ้าของ (ฉบับร่าง)")
    sce_df = fs_res["changes_in_equity"]
    st.dataframe(sce_df, use_container_width=True, hide_index=True)

with t_cf:
    st.subheader(f"งบกระแสเงินสด (ฉบับร่าง) — วิธี: {setup.cashflow_method}")
    if not setup.prepare_cashflow:
        st.info("ผู้ใช้เลือกไม่จัดทำงบกระแสเงินสดในหน้า 00_Entity_and_Framework_Setup")
    elif cf_res["status"] == "Insufficient Data":
        st.warning(f"⚠️ {cf_res['message']}")
    else:
        if cf_res["message"]:
            st.info(f"📌 {cf_res['message']}")
        st.dataframe(cf_res["cashflow_df"], use_container_width=True, hide_index=True)
        if cf_res["reconciled"]:
            st.success(f"✅ เงินสดปลายงวดตรงกันระหว่าง Cash Flow ({cf_res['ending_cash_cf']:,.2f}) และ Balance Sheet ({cf_res['ending_cash_bs']:,.2f})")
        else:
            st.error(f"❌ เงินสดปลายงวดมีผลต่าง: CF={cf_res['ending_cash_cf']:,.2f} vs BS={cf_res['ending_cash_bs']:,.2f}")

with t_det:
    st.subheader("Detail Schedules แยกตามหมวดบัญชี (D_*)")
    ds_list = sorted(adjusted_tb["Detail_Sheet"].unique().tolist())
    sel_ds = st.selectbox("เลือก Detail Schedule", options=ds_list)
    sub_ds = adjusted_tb[adjusted_tb["Detail_Sheet"] == sel_ds]
    st.dataframe(
        sub_ds[["Account_Code", "Account_Name", "Grouping", "Sub_Grouping", "FS_Line_Item", "Unadjusted_Net", "Adjustment_Debit", "Adjustment_Credit", "Adjusted_FS_Amount", "Prior_Balance", "Note_No", "Mapping_Status"]],
        use_container_width=True,
        hide_index=True,
    )

if not fs_res["unmapped"].empty:
    st.error("⚠️ รายการที่ยังไม่ได้ Mapping (แสดงแยกต่างหาก — ห้ามนำไปออกงบฉบับ Final)")
    st.dataframe(fs_res["unmapped"][["Account_Code", "Account_Name", "Adjusted_Net", "Mapping_Status"]], use_container_width=True, hide_index=True)

render_page_review_signoff("fs", lang)
