from __future__ import annotations

import streamlit as st

from src.accounting_rules import compute_adjusted_tb
from src.notes import build_notes_and_checklist
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="07 Notes to FS", page_icon="📑", layout="wide")
setup = render_sidebar_and_header("notes", "07. หมายเหตุประกอบงบการเงินและ Disclosure Checklist", "07. Notes to Financial Statements & Checklist")
lang = setup.language

tb_df = st.session_state["tb_normalized"]
mapping_df = st.session_state["coa_mapping"]
adj_tb = compute_adjusted_tb(tb_df, st.session_state["adjustments"], mapping_df) if not tb_df.empty else tb_df

if st.session_state["notes_index"].empty or st.button("🔄 สร้าง/อัปเดตร่างหมายเหตุจาก Adjusted TB", type="primary"):
    idx_df, drf_df = build_notes_and_checklist(adj_tb, setup, st.session_state["notes_index"])
    st.session_state["notes_index"] = idx_df
    st.session_state["notes_draft"] = drf_df

idx_df = st.session_state["notes_index"]
drf_df = st.session_state["notes_draft"]

st.caption("หมายเหตุทุกข้อที่ข้อมูลไม่ครบจะแสดง `[รอข้อมูลจากฝ่ายบริหาร]` และห้ามถือว่าได้รับการยืนยันจนกว่าผู้ทำบัญชีและผู้สอบบัญชีจะสอบทานแล้ว")

t1, t2 = st.tabs(["1) Disclosure Checklist (Notes_Index)", "2) ร่างหมายเหตุประกอบงบการเงิน (Notes_Draft)"])
with t1:
    edited_idx = st.data_editor(
        idx_df,
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["Auto-populated", "Requires management input", "Requires supporting schedule", "Requires CPA review", "Not applicable"],
            ),
            "TB_Amount": st.column_config.NumberColumn("TB Amount", format="%.2f", disabled=True),
        },
        use_container_width=True,
        hide_index=True,
        key="notes_idx_ed",
    )
    if st.button("💾 บันทึก Disclosure Checklist"):
        st.session_state["notes_index"] = edited_idx
        log_change("Notes", "Update Checklist", f"{len(edited_idx)} notes")
        st.success("บันทึก Checklist สำเร็จ")
    st.download_button("⬇️ ดาวน์โหลด Notes_Index (.csv)", edited_idx.to_csv(index=False).encode("utf-8-sig"), "Notes_Index.csv", "text/csv")

with t2:
    edited_drf = st.data_editor(
        drf_df,
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["Auto-populated", "Requires management input", "Requires supporting schedule", "Requires CPA review", "Not applicable"],
            ),
        },
        use_container_width=True,
        hide_index=True,
        key="notes_drf_ed",
    )
    if st.button("💾 บันทึกร่างหมายเหตุ"):
        st.session_state["notes_draft"] = edited_drf
        log_change("Notes", "Update Notes Draft", f"{len(edited_drf)} notes")
        st.success("บันทึกร่างหมายเหตุสำเร็จ")
    st.download_button("⬇️ ดาวน์โหลด Notes_Draft (.csv)", edited_drf.to_csv(index=False).encode("utf-8-sig"), "Notes_Draft.csv", "text/csv")

render_page_review_signoff("notes", lang)
