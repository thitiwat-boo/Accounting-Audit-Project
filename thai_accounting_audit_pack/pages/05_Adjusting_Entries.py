from __future__ import annotations

import pandas as pd
import streamlit as st

from src.accounting_rules import (
    ADJUSTMENT_COLUMNS,
    compute_adjusted_tb,
    empty_adjustments_df,
    generate_proposed_adjustments,
)
from src.financial_statements import build_financial_statements
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="05 Adjusting Entries", page_icon="📝", layout="wide")
setup = render_sidebar_and_header("adjustments", "05. รายการปรับปรุงและสอบทานปิดบัญชี (Adjusting Entries)", "05. Adjusting Entries & Closing Review")
lang = setup.language

tb_df = st.session_state["tb_normalized"]
gl_df = st.session_state["gl_normalized"]
mapping_df = st.session_state["coa_mapping"]

if tb_df.empty:
    st.info("กรุณานำเข้าข้อมูล Trial Balance ในหน้า `01_นำเข้าข้อมูล` ก่อน")
    render_page_review_signoff("adjustments", lang)
    st.stop()

if st.session_state["adjustments"].empty:
    st.session_state["adjustments"] = empty_adjustments_df()

c_btn1, c_btn2 = st.columns(2)
with c_btn1:
    if st.button("🤖 สร้างข้อเสนอรายการปรับปรุง (Proposed Adjustments)", type="primary", use_container_width=True):
        props = generate_proposed_adjustments(tb_df, gl_df, mapping_df, setup.period_end)
        curr = st.session_state["adjustments"]
        existing_ids = set(curr["JE_Number"]) if not curr.empty else set()
        new_rows = props[~props["JE_Number"].isin(existing_ids)]
        if not new_rows.empty:
            st.session_state["adjustments"] = pd.concat([curr, new_rows], ignore_index=True)
            log_change("Adjusting Entries", "Generate Proposals", f"{len(new_rows)} items")
        st.rerun()
with c_btn2:
    st.caption("เฉพาะรายการที่มีสถานะ `Approved` หรือ `Posted` เท่านั้นที่จะถูกคำนวณเข้า `Adjusted_TB` — ข้อมูลต้นฉบับใน `TB_Original` จะไม่ถูกแก้ไข")

st.subheader("1) เพิ่มรายการปรับปรุงด้วยตนเอง (Manual Adjusting Entry)")
acct_opts = sorted(set(tb_df["Account_Code"].astype(str)) | set(mapping_df["Account_Code"].astype(str)))
categories = [
    "Accrued expenses",
    "Prepaid expense amortization",
    "Depreciation",
    "Allowance for doubtful accounts",
    "Inventory write-down",
    "Foreign exchange revaluation",
    "Tax provision",
    "Interest accrual",
    "Revenue cut-off",
    "Reclassification between current and non-current",
    "Related-party reclassification",
    "Prior-period error adjustment",
    "Other",
]

with st.form("add_aje_form"):
    f1, f2, f3, f4 = st.columns(4)
    je_no = f1.text_input("JE Number", value=f"AJE-{len(st.session_state['adjustments'])+1:03d}")
    je_date = f2.date_input("JE Date", value=setup.period_end)
    cat = f3.selectbox("Category", options=categories)
    amt = f4.number_input("Amount (THB)", min_value=0.0, value=0.0, step=1000.0)

    f5, f6, f7 = st.columns(3)
    dr_acct = f5.selectbox("Debit Account", options=acct_opts)
    cr_acct = f6.selectbox("Credit Account", options=acct_opts)
    status = f7.selectbox("Status", options=["Draft", "Proposed", "Approved", "Posted", "Rejected"])

    desc = st.text_input("Description / คำอธิบายรายการ")
    f8, f9, f10 = st.columns(3)
    reason = f8.text_input("Reason / เหตุผลการปรับปรุง")
    std_ref = f9.text_input("Standard / Policy Reference", value="TFRS for NPAEs")
    supp_ref = f10.text_input("Supporting Document Reference")

    if st.form_submit_button("➕ เพิ่มรายการปรับปรุง"):
        new_entry = pd.DataFrame(
            [
                {
                    "JE_Number": je_no,
                    "JE_Date": str(je_date),
                    "Category": cat,
                    "Debit_Account": dr_acct,
                    "Credit_Account": cr_acct,
                    "Amount": float(amt),
                    "Description": desc,
                    "Reason": reason,
                    "Standard_Policy_Ref": std_ref,
                    "Assumptions": "User-entered adjustment",
                    "Missing_Info": "",
                    "Prepared_By": "Accountant",
                    "Reviewed_By": "",
                    "Status": status,
                    "Supporting_Doc_Ref": supp_ref,
                }
            ],
            columns=ADJUSTMENT_COLUMNS,
        )
        st.session_state["adjustments"] = pd.concat([st.session_state["adjustments"], new_entry], ignore_index=True)
        log_change("Adjusting Entries", "Add JE", je_no, new_value=f"{dr_acct}/{cr_acct} {amt:,.2f} ({status})")
        st.success(f"เพิ่มรายการ {je_no} แล้ว")
        st.rerun()

st.subheader("2) ตารางรายการปรับปรุง (แก้ไขจำนวนเงินและเปลี่ยนสถานะอนุมัติ)")
adj_df = st.session_state["adjustments"]
edited_adj = st.data_editor(
    adj_df,
    column_config={
        "Amount": st.column_config.NumberColumn("Amount", format="%.2f"),
        "Status": st.column_config.SelectboxColumn("Status", options=["Draft", "Proposed", "Approved", "Posted", "Rejected"]),
    },
    use_container_width=True,
    hide_index=True,
    key="aje_editor",
)
if st.button("💾 บันทึกสถานะและการแก้ไขรายการปรับปรุง"):
    st.session_state["adjustments"] = edited_adj
    log_change("Adjusting Entries", "Update Table", f"{len(edited_adj)} rows")
    st.success("บันทึกการแก้ไขแล้ว")
    st.rerun()

st.subheader("3) ผลกระทบก่อนและหลังปรับปรุงต่องบการเงิน (Before vs After Impact)")
unadj_tb = compute_adjusted_tb(tb_df, empty_adjustments_df(), mapping_df)
adj_tb = compute_adjusted_tb(tb_df, st.session_state["adjustments"], mapping_df)
fs_before = build_financial_statements(unadj_tb, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"])
fs_after = build_financial_statements(adj_tb, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"])

rb = fs_before.get("reconciliations", {})
ra = fs_after.get("reconciliations", {})
impact_df = pd.DataFrame(
    [
        {"Metric": "รวมสินทรัพย์ (Total Assets)", "Before_Adjustments": rb.get("total_assets", 0.0), "After_Adjustments": ra.get("total_assets", 0.0), "Impact": ra.get("total_assets", 0.0) - rb.get("total_assets", 0.0)},
        {"Metric": "รวมหนี้สิน (Total Liabilities)", "Before_Adjustments": rb.get("total_liabilities", 0.0), "After_Adjustments": ra.get("total_liabilities", 0.0), "Impact": ra.get("total_liabilities", 0.0) - rb.get("total_liabilities", 0.0)},
        {"Metric": "รวมส่วนของเจ้าของ (Total Equity)", "Before_Adjustments": rb.get("total_equity", 0.0), "After_Adjustments": ra.get("total_equity", 0.0), "Impact": ra.get("total_equity", 0.0) - rb.get("total_equity", 0.0)},
        {"Metric": "รายได้หลัก (Revenue)", "Before_Adjustments": rb.get("revenue", 0.0), "After_Adjustments": ra.get("revenue", 0.0), "Impact": ra.get("revenue", 0.0) - rb.get("revenue", 0.0)},
        {"Metric": "กำไรสุทธิ (Net Income)", "Before_Adjustments": rb.get("net_income", 0.0), "After_Adjustments": ra.get("net_income", 0.0), "Impact": ra.get("net_income", 0.0) - rb.get("net_income", 0.0)},
    ]
)
st.dataframe(impact_df, use_container_width=True, hide_index=True)

with st.expander("ดูตาราง Adjusted Trial Balance (เปรียบเทียบ Unadjusted / Adjustments / Adjusted)"):
    st.dataframe(adj_tb, use_container_width=True, hide_index=True)
    st.download_button("⬇️ ดาวน์โหลด Adjusted_TB (.csv)", adj_tb.to_csv(index=False).encode("utf-8-sig"), "Adjusted_TB.csv", "text/csv")

render_page_review_signoff("adjustments", lang)
