from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

from src.config_loader import CONFIG_DIR, get_grouping_master, get_grouping_master_df
from src.mapping import build_initial_coa_mapping, detect_mapping_conflicts_and_unmapped
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="04 ผังบัญชีและ Mapping", page_icon="🧭", layout="wide")
setup = render_sidebar_and_header("mapping", "04. ผังบัญชีและ Mapping Wizard (5 ระดับ)", "04. Chart of Accounts & 5-Level Mapping")
lang = setup.language

tb_df = st.session_state["tb_normalized"]
gl_df = st.session_state["gl_normalized"]

if tb_df.empty:
    st.info("กรุณานำเข้าข้อมูล Trial Balance ในหน้า `01_นำเข้าข้อมูล` ก่อน")
    render_page_review_signoff("mapping", lang)
    st.stop()

if st.session_state["coa_mapping"].empty:
    st.session_state["coa_mapping"] = build_initial_coa_mapping(tb_df, gl_df, setup.materiality_amount)

mapping_df = st.session_state["coa_mapping"]

# Template & Custom Mapping Upload
c_t1, c_t2, c_t3 = st.columns([1, 1, 2])
with c_t1:
    tpl_path = CONFIG_DIR / "account_mapping_template.xlsx"
    if tpl_path.exists():
        st.download_button(
            "⬇️ Template Mapping (.xlsx)",
            data=tpl_path.read_bytes(),
            file_name="account_mapping_template.xlsx",
            use_container_width=True,
        )
with c_t2:
    if st.button("🤖 รัน Mapping Wizard ใหม่ (เฉพาะบัญชียังไม่ Confirmed)", use_container_width=True):
        st.session_state["coa_mapping"] = build_initial_coa_mapping(
            tb_df, gl_df, setup.materiality_amount, st.session_state["coa_mapping"]
        )
        log_change("COA Mapping", "Run Mapping Wizard", "Unconfirmed accounts")
        st.rerun()
with c_t3:
    up_map = st.file_uploader("อัปโหลด Mapping ที่บันทึกไว้ (.xlsx)", type=["xlsx"])
    if up_map is not None:
        try:
            imp_df = pd.read_excel(up_map, sheet_name=0)
            if "Account_Code" in imp_df.columns and "FS_Line_Item" in imp_df.columns:
                st.session_state["coa_mapping"] = imp_df
                log_change("COA Mapping", "Import Mapping Excel", up_map.name)
                st.success("นำเข้าตาราง Mapping สำเร็จ")
                st.rerun()
            else:
                st.error("ไฟล์ Mapping ต้องมีคอลัมน์ Account_Code และ FS_Line_Item")
        except Exception as exc:
            st.error(f"อ่านไฟล์ไม่สำเร็จ: {exc}")

st.caption("หมายเหตุ: รายการที่ระบุว่า `AI Suggested` หรือ `Rule Based` เป็นข้อเสนอเพื่อสอบทาน ห้ามถือเป็น Final จนกว่าผู้ทำบัญชีจะยืนยันเป็น `Approved`")

hierarchy = get_grouping_master().get("hierarchy", [])
grouping_opts = sorted({h["grouping"] for h in hierarchy})
subgrp_opts = sorted({h["sub_grouping"] for h in hierarchy})
line_opts = sorted({h["fs_line_item"] for h in hierarchy})
dsheet_opts = sorted({h["detail_sheet"] for h in hierarchy})

# Merge Net_Balance for preview in wizard
bal_map = tb_df.groupby("Account_Code")["Net_Balance"].sum().to_dict()
display_df = mapping_df.copy()
display_df.insert(2, "TB_Net_Balance", display_df["Account_Code"].map(bal_map).fillna(0.0))

edited = st.data_editor(
    display_df,
    column_config={
        "TB_Net_Balance": st.column_config.NumberColumn("TB Net Balance", format="%.2f", disabled=True),
        "Normal_Balance": st.column_config.SelectboxColumn("Normal Balance", options=["Debit", "Credit"]),
        "Account_Type": st.column_config.SelectboxColumn("Account Type", options=["Asset", "Liability", "Equity", "Revenue", "Expense", "Contra", "Memo"]),
        "Grouping": st.column_config.SelectboxColumn("Grouping", options=grouping_opts),
        "Sub_Grouping": st.column_config.SelectboxColumn("Sub Grouping", options=subgrp_opts),
        "FS_Line_Item": st.column_config.SelectboxColumn("FS Line Item", options=line_opts),
        "Detail_Sheet": st.column_config.SelectboxColumn("Detail Sheet", options=dsheet_opts),
        "Mapping_Method": st.column_config.SelectboxColumn("Method", options=["User Confirmed", "Rule Based", "AI Suggested"]),
        "Reviewer_Status": st.column_config.SelectboxColumn("Status", options=["Approved", "ต้องยืนยัน", "Unmapped", "Rejected"]),
        "Confidence_Score": st.column_config.NumberColumn("Confidence %", disabled=True),
    },
    use_container_width=True,
    hide_index=True,
    key="coa_editor",
)

b1, b2, b3 = st.columns(3)
with b1:
    if st.button("💾 บันทึกการแก้ไข Mapping", type="primary", use_container_width=True):
        clean_df = edited.drop(columns=["TB_Net_Balance"], errors="ignore")
        # Update FS_Sign automatically based on Grouping
        sign_map = {h["grouping"]: h["fs_sign"] for h in hierarchy}
        clean_df["FS_Sign"] = clean_df["Grouping"].map(sign_map).fillna(clean_df["FS_Sign"])
        st.session_state["coa_mapping"] = clean_df
        st.session_state["grouping_version"] = f"v1.{len(st.session_state['change_log']) + 1}"
        log_change("COA Mapping", "Save Edits", f"{len(clean_df)} accounts", new_value=st.session_state["grouping_version"])
        st.success("บันทึก Mapping สำเร็จ!")
        st.rerun()
with b2:
    if st.button("✅ ยืนยันทั้งหมดที่มี Confidence >= 75% (Approve High-Confidence)", use_container_width=True):
        clean_df = edited.drop(columns=["TB_Net_Balance"], errors="ignore")
        mask = (clean_df["Confidence_Score"] >= 75) & (clean_df["Reviewer_Status"] != "Unmapped")
        clean_df.loc[mask, "Reviewer_Status"] = "Approved"
        clean_df.loc[mask, "Mapping_Method"] = "User Confirmed"
        st.session_state["coa_mapping"] = clean_df
        log_change("COA Mapping", "Bulk Approve >=75%", f"{int(mask.sum())} accounts")
        st.rerun()
with b3:
    st.download_button(
        "⬇️ ดาวน์โหลด COA_Mapping (.csv)",
        mapping_df.to_csv(index=False).encode("utf-8-sig"),
        "COA_Mapping.csv",
        "text/csv",
        use_container_width=True,
    )

unmapped_df, conflicts_df = detect_mapping_conflicts_and_unmapped(st.session_state["coa_mapping"], tb_df)
st.divider()
u1, u2 = st.columns(2)
with u1:
    st.subheader(f"บัญชี Unmapped / บัญชีพัก ({len(unmapped_df)})")
    if unmapped_df.empty:
        st.success("ไม่มีบัญชี Unmapped หรือบัญชีพัก")
    else:
        st.error("ห้ามออกงบการเงินฉบับ Final จนกว่าจะจัดประเภทบัญชีเหล่านี้")
        st.dataframe(unmapped_df[["Account_Code", "Account_Name", "Net_Balance", "Reviewer_Status"]], use_container_width=True, hide_index=True)
with u2:
    st.subheader(f"Mapping Conflicts / รอยืนยัน ({len(conflicts_df)})")
    if conflicts_df.empty:
        st.success("ทุกบัญชีได้รับการยืนยัน (Approved) และไม่พบ Conflict")
    else:
        st.warning("บัญชีที่ยังไม่ Approved หรือมียอดกลับด้านกับ Normal Balance:")
        st.dataframe(conflicts_df[["Account_Code", "Account_Name", "Net_Balance", "Reviewer_Status", "Conflict_Reason"]], use_container_width=True, hide_index=True)

with st.expander("📚 ดู Grouping_Master (โครงสร้างลำดับชั้น 5 ระดับ)"):
    st.dataframe(get_grouping_master_df(), use_container_width=True, hide_index=True)

render_page_review_signoff("mapping", lang)
