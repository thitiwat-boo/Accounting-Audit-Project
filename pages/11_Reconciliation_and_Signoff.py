from __future__ import annotations

import pandas as pd
import streamlit as st

from src.accounting_rules import compute_adjusted_tb
from src.cashflow import build_cash_flow_statement
from src.financial_statements import build_financial_statements
from src.mapping import detect_mapping_conflicts_and_unmapped
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="11 Reconciliation & Sign-off", page_icon="✅", layout="wide")
setup = render_sidebar_and_header("reconcile", "11. Reconciliation & Sign-off (กระทบยอดทุกงบก่อนส่งออก)", "11. Reconciliation & Sign-off")
lang = setup.language

tb_df = st.session_state["tb_normalized"]
gl_df = st.session_state["gl_normalized"]
mapping_df = st.session_state["coa_mapping"]

if tb_df.empty:
    st.info("กรุณานำเข้าข้อมูล TB/GL ก่อน")
    render_page_review_signoff("reconcile", lang)
    st.stop()

adjusted_tb = compute_adjusted_tb(tb_df, st.session_state["adjustments"], mapping_df)
fs_res = build_financial_statements(adjusted_tb, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"])
cf_res = build_cash_flow_statement(adjusted_tb, gl_df, fs_res, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"])
unmapped_df, conflicts_df = detect_mapping_conflicts_and_unmapped(mapping_df, tb_df)

rec = fs_res["reconciliations"]
tb_dr = float(tb_df["Debit"].sum())
tb_cr = float(tb_df["Credit"].sum())
atb_dr = float(adjusted_tb["Adjusted_Debit"].sum())
atb_cr = float(adjusted_tb["Adjusted_Credit"].sum())

# TB vs GL account overlap
tb_codes = set(tb_df["Account_Code"].astype(str))
gl_codes = set(gl_df["Account_Code"].astype(str)) if not gl_df.empty else set()
gl_only_cnt = len(gl_codes - tb_codes) if not gl_df.empty else 0

# Equity reconciliation
sce_df = fs_res["changes_in_equity"]
sce_end_eq = float(sce_df.loc[sce_df["Item"] == "ยอดคงเหลือปลายงวด", "Total_Equity"].iloc[0]) if not sce_df.empty else 0.0
bs_eq = float(rec.get("total_equity", 0.0))

# Adjusting entries balance
adj_df = st.session_state["adjustments"]
adj_active = adj_df[adj_df["Status"].isin(["Approved", "Posted"])] if not adj_df.empty else pd.DataFrame()
adj_dr_tot = float(adjusted_tb["Adjustment_Debit"].sum())
adj_cr_tot = float(adjusted_tb["Adjustment_Credit"].sum())

checks = [
    {"Reconciliation_Item": "1. Trial Balance (Debit = Credit)", "Left_Value": tb_dr, "Right_Value": tb_cr, "Difference": round(tb_dr - tb_cr, 2), "Status": "Pass" if abs(tb_dr - tb_cr) < 0.01 else "Error"},
    {"Reconciliation_Item": "2. Adjusted TB (Debit = Credit)", "Left_Value": atb_dr, "Right_Value": atb_cr, "Difference": round(atb_dr - atb_cr, 2), "Status": "Pass" if abs(atb_dr - atb_cr) < 0.01 else "Error"},
    {"Reconciliation_Item": "3. TB to GL Account Coverage (GL accounts missing from TB)", "Left_Value": len(tb_codes), "Right_Value": gl_only_cnt, "Difference": gl_only_cnt, "Status": "Pass" if (not gl_df.empty and gl_only_cnt == 0) else ("Warning" if gl_df.empty else "Error")},
    {"Reconciliation_Item": "4. Balance Sheet Equation (Assets vs Liab + Equity)", "Left_Value": rec.get("total_assets", 0.0), "Right_Value": rec.get("total_liabilities", 0.0) + bs_eq, "Difference": rec.get("bs_balance_diff", 0.0), "Status": "Pass" if abs(rec.get("bs_balance_diff", 0.0)) < 0.01 else "Error"},
    {"Reconciliation_Item": "5. Equity Movement Reconciliation (BS Equity vs SCE Ending)", "Left_Value": bs_eq, "Right_Value": sce_end_eq, "Difference": round(bs_eq - sce_end_eq, 2), "Status": "Pass" if abs(bs_eq - sce_end_eq) < 0.01 else "Error"},
    {"Reconciliation_Item": "6. Cash Reconciliation (Cash Flow Ending vs BS Cash)", "Left_Value": cf_res.get("ending_cash_cf", 0.0), "Right_Value": rec.get("cash_ending", 0.0), "Difference": round(cf_res.get("ending_cash_cf", 0.0) - rec.get("cash_ending", 0.0), 2) if cf_res.get("status") != "Insufficient Data" else 0.0, "Status": "Pass" if cf_res.get("reconciled") else "Warning"},
    {"Reconciliation_Item": "7. Unmapped & Conflict Accounts (Count)", "Left_Value": len(unmapped_df), "Right_Value": len(conflicts_df), "Difference": len(unmapped_df) + len(conflicts_df), "Status": "Pass" if (len(unmapped_df) == 0 and len(conflicts_df) == 0) else "Warning"},
    {"Reconciliation_Item": "8. Adjusting Entries Reconciliation (Dr = Cr)", "Left_Value": adj_dr_tot, "Right_Value": adj_cr_tot, "Difference": round(adj_dr_tot - adj_cr_tot, 2), "Status": "Pass" if abs(adj_dr_tot - adj_cr_tot) < 0.01 else "Error"},
]
rec_df = pd.DataFrame(checks)
st.dataframe(rec_df, use_container_width=True, hide_index=True)

st.subheader("สถานะการสอบทานรายหน้า (Page Sign-off Summary)")
st.json(st.session_state["review_signoffs"])

st.subheader("Change Log (ประวัติการแก้ไขและยืนยัน)")
if st.session_state["change_log"]:
    st.dataframe(pd.DataFrame(st.session_state["change_log"]), use_container_width=True, hide_index=True)

render_page_review_signoff("reconcile", lang)
