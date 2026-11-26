from __future__ import annotations

import pandas as pd
import streamlit as st

from src.accounting_rules import compute_adjusted_tb
from src.auditor_report import OPINION_CHOICES, build_draft_auditor_report, collect_unresolved_issues
from src.financial_statements import build_financial_statements
from src.mapping import detect_mapping_conflicts_and_unmapped
from src.notes import build_notes_and_checklist
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="09 Draft Auditor Report", page_icon="⚖️", layout="wide")
setup = render_sidebar_and_header("auditor_report", "09. ร่างรายงานผู้สอบบัญชีรับอนุญาต (Draft for CPA Review)", "09. Draft Auditor's Report")
lang = setup.language

st.error(
    "🔒 กฎบังคับทางวิชาชีพ: เอกสารนี้สร้างได้เฉพาะสถานะ `Draft for CPA Review` ห้ามระบบเลือกประเภทความเห็นเอง ห้ามสร้างชื่อหรือเลขทะเบียนผู้สอบบัญชีรับอนุญาต และห้ามอ้างว่าเป็นรายงานที่ลงนามแล้ว"
)

tb_df = st.session_state["tb_normalized"]
mapping_df = st.session_state["coa_mapping"]
adj_tb = compute_adjusted_tb(tb_df, st.session_state["adjustments"], mapping_df) if not tb_df.empty else pd.DataFrame()
fs_res = build_financial_statements(adj_tb, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"]) if not adj_tb.empty else {}
unmapped_df, _ = detect_mapping_conflicts_and_unmapped(mapping_df, tb_df) if not tb_df.empty else (pd.DataFrame(), pd.DataFrame())
notes_idx = st.session_state["notes_index"]
if notes_idx.empty and not adj_tb.empty:
    notes_idx, _ = build_notes_and_checklist(adj_tb, setup)

unresolved = collect_unresolved_issues(
    st.session_state["dq_report"],
    unmapped_df,
    st.session_state["adjustments"],
    fs_res,
    notes_idx,
)

with st.expander(f"⚠️ รายการ Unresolved Issues & Scope Limitations ({len(unresolved)})", expanded=True):
    for issue in unresolved:
        st.markdown(f"- {issue}")

c1, c2 = st.columns([2, 1])
with c1:
    sel_op = st.selectbox(
        "ประเภทความเห็น (CPA ต้องเลือกด้วยตนเองเท่านั้น)",
        options=OPINION_CHOICES,
        index=OPINION_CHOICES.index(st.session_state["auditor_opinion"]) if st.session_state["auditor_opinion"] in OPINION_CHOICES else 0,
    )
    if sel_op != st.session_state["auditor_opinion"]:
        st.session_state["auditor_opinion"] = sel_op
        log_change("Auditor Report", "Select Draft Opinion", "Opinion", new_value=sel_op)
with c2:
    inc_gc = st.checkbox("เพิ่มย่อหน้า Going Concern (TSA 570)", value=False)
    inc_kam = st.checkbox("เพิ่มย่อหน้า KAM (TSA 701 - ถ้าเข้าเกณฑ์)", value=setup.is_listed)
    inc_oth = st.checkbox("เพิ่มย่อหน้าข้อมูลอื่น (TSA 720)", value=False)

draft_df, ref_df = build_draft_auditor_report(
    setup,
    unresolved,
    selected_opinion=sel_op,
    include_kam=inc_kam,
    include_going_concern=inc_gc,
    include_other_info=inc_oth,
    cpa_custom_edits=st.session_state["auditor_edits"],
)

st.subheader("ร่างย่อหน้ารายงานผู้สอบบัญชี (CPA แก้ไขถ้อยคำได้ในคอลัมน์ CPA_Edit)")
edited_report = st.data_editor(
    draft_df,
    column_config={
        "Generated_Text": st.column_config.TextColumn("Generated Text (Draft)", width="large", disabled=True),
        "CPA_Edit": st.column_config.TextColumn("CPA Edit (แก้ไขโดยผู้สอบบัญชี)", width="large"),
        "Approval_Status": st.column_config.TextColumn("Status", disabled=True),
    },
    use_container_width=True,
    hide_index=True,
    key="aud_report_editor",
)
if st.button("💾 บันทึกถ้อยคำ CPA Edit"):
    edits = {str(r["Paragraph_ID"]): str(r["CPA_Edit"]) for _, r in edited_report.iterrows() if str(r["CPA_Edit"]).strip()}
    st.session_state["auditor_edits"] = edits
    log_change("Auditor Report", "Save CPA Edits", f"{len(edits)} paragraphs edited")
    st.success("บันทึกถ้อยคำแก้ไขของ CPA เรียบร้อย")

st.download_button(
    "⬇️ ดาวน์โหลด Draft Auditor Report (.csv)",
    edited_report.to_csv(index=False).encode("utf-8-sig"),
    "Auditor_Report_Draft.csv",
    "text/csv",
)

with st.expander("📚 Auditor_Report_Ref (แหล่งอ้างอิงมาตรฐาน TFAC และประกาศ DBD)"):
    st.dataframe(ref_df, use_container_width=True, hide_index=True)

render_page_review_signoff("auditor_report", lang)
