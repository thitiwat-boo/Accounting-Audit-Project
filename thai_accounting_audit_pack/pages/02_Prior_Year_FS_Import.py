from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config_loader import SAMPLE_DIR, get_grouping_master
from src.prior_year import (
    extract_prior_year_excel,
    extract_prior_year_pdf,
    reconcile_prior_year_with_opening_tb,
    verify_prior_year_entity_match,
)
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="02 Prior Year FS Import", page_icon="🗂️", layout="wide")
setup = render_sidebar_and_header("prior_year", "02. นำเข้าและกระทบยอดงบการเงินปีก่อน (Prior Year FS)", "02. Prior Year Financial Statements Import")
lang = setup.language

mode = st.radio(
    "บทบาทของข้อมูลปีก่อนในงบฉบับปัจจุบัน",
    options=["Comparative Source", "Reference Only", "Do Not Use"],
    index=["Comparative Source", "Reference Only", "Do Not Use"].index(st.session_state["prior_year_mode"]),
    horizontal=True,
)
st.session_state["prior_year_mode"] = mode

c_up, c_samp = st.columns([3, 1])
with c_up:
    py_file = st.file_uploader("อัปโหลดงบการเงินปีก่อน (.xlsx หรือ .pdf ทั้ง Text PDF / Scan PDF OCR)", type=["xlsx", "xls", "pdf"])
with c_samp:
    st.write("")
    st.write("")
    load_sample_py = st.button("📄 โหลด Sample Prior Year (.pdf)", use_container_width=True)

if py_file is not None:
    raw_bytes = py_file.read()
    fname = py_file.name
    if fname.lower().endswith(".pdf"):
        ext_df, meta = extract_prior_year_pdf(raw_bytes, fname)
    elif fname.lower().endswith(".xlsx"):
        ext_df, meta = extract_prior_year_excel(raw_bytes, fname)
    else:
        st.error("ไฟล์ .xls รุ่นเก่าไม่รองรับในสภาพแวดล้อมนี้โดยตรง กรุณาบันทึกเป็น .xlsx หรือ .pdf ก่อนอัปโหลด")
        ext_df, meta = pd.DataFrame(), {}

    if not ext_df.empty:
        st.session_state["prior_year_extracted"] = ext_df
        st.session_state["prior_year_meta"] = meta
        rev_df = reconcile_prior_year_with_opening_tb(ext_df, st.session_state["tb_normalized"], st.session_state["coa_mapping"])
        st.session_state["prior_year_review"] = rev_df
        log_change("Prior Year", "Import Prior Year FS", fname, new_value=f"{len(ext_df)} items ({meta.get('file_type')})")
        st.success(f"อ่านข้อมูลจาก {fname} ({meta.get('file_type')}) ได้ {len(ext_df)} รายการ — กรุณาตรวจสอบและยืนยันยอดด้านล่าง")
    elif meta.get("ocr_warning"):
        st.error(meta["ocr_warning"])
    else:
        st.warning("ไม่พบรายการตัวเลขที่ดึงได้จากไฟล์นี้ กรุณาตรวจสอบรูปแบบไฟล์")

elif load_sample_py:
    p_pdf = SAMPLE_DIR / "sample_prior_year_fs.pdf"
    if p_pdf.exists():
        ext_df, meta = extract_prior_year_pdf(p_pdf.read_bytes(), p_pdf.name)
        st.session_state["prior_year_extracted"] = ext_df
        st.session_state["prior_year_meta"] = meta
        st.session_state["prior_year_review"] = reconcile_prior_year_with_opening_tb(
            ext_df, st.session_state["tb_normalized"], st.session_state["coa_mapping"]
        )
        log_change("Prior Year", "Load Sample Prior Year PDF", p_pdf.name, new_value=f"{len(ext_df)} items")
        st.success("โหลดงบปีก่อนตัวอย่าง (.pdf) สำเร็จ")
        st.rerun()

ext_df = st.session_state["prior_year_extracted"]
meta = st.session_state["prior_year_meta"]

if not ext_df.empty:
    ent_check = verify_prior_year_entity_match(
        meta.get("header_preview", ""), setup.entity_name, setup.registration_no, setup.comparative_period_label
    )
    st.subheader("1) ตรวจสอบความเป็นนิติบุคคลเดียวกันและงวดเปรียบเทียบ")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Entity Name Match", "✅ Match" if ent_check["entity_name_matched"] else "⚠️ Needs Verification")
    m2.metric("Reg No Match", "✅ Match" if ent_check["reg_no_matched"] else "➖ N/A / Check")
    m3.metric("Comparative Period Match", "✅ Match" if ent_check["comparative_period_matched"] else "⚠️ Check")
    m4.metric("OCR Used?", "⚠️ OCR (ห้ามใช้เป็น Final โดยไม่ตรวจ)" if meta.get("ocr_used") else "Text / Excel")
    st.caption(f"Header Preview: {meta.get('header_preview', '')}")

    st.subheader("2) จับคู่รายการปีก่อนกับ FS Line Item และยืนยันยอดเปรียบเทียบ")
    fs_line_choices = [""] + sorted({r["fs_line_item"] for r in get_grouping_master().get("hierarchy", [])})

    edited_ext = st.data_editor(
        ext_df,
        column_config={
            "Mapped_FS_Line_Item": st.column_config.SelectboxColumn("Mapped FS Line Item", options=fs_line_choices),
            "UserConfirmed": st.column_config.CheckboxColumn("ยืนยันใช้ยอด (UserConfirmed)"),
            "ExtractedAmount": st.column_config.NumberColumn("Extracted Amount", format="%.2f"),
        },
        use_container_width=True,
        hide_index=True,
        key="py_editor",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("💾 บันทึกการจับคู่ & กระทบยอดกับ TB Opening", type="primary"):
            st.session_state["prior_year_extracted"] = edited_ext
            rev_df = reconcile_prior_year_with_opening_tb(
                edited_ext, st.session_state["tb_normalized"], st.session_state["coa_mapping"]
            )
            st.session_state["prior_year_review"] = rev_df
            log_change("Prior Year", "Update Mapping & Confirm", f"{int(edited_ext['UserConfirmed'].sum())} confirmed items")
            st.success("บันทึกและกระทบยอดเรียบร้อย!")
            st.rerun()
    with col_b:
        if st.button("☑️ ยืนยันทุกรายการ (Confirm All Non-OCR Rows)"):
            edited_ext["UserConfirmed"] = edited_ext["ExtractionMethod"].apply(lambda m: "OCR" not in str(m))
            st.session_state["prior_year_extracted"] = edited_ext
            st.session_state["prior_year_review"] = reconcile_prior_year_with_opening_tb(
                edited_ext, st.session_state["tb_normalized"], st.session_state["coa_mapping"]
            )
            st.rerun()

    rev_df = st.session_state["prior_year_review"]
    if not rev_df.empty:
        st.subheader("3) Prior Year vs Opening/Prior TB Reconciliation")
        st.dataframe(rev_df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ ดาวน์โหลด Prior_Year_Review (.csv)",
            rev_df.to_csv(index=False).encode("utf-8-sig"),
            "Prior_Year_Review.csv",
            "text/csv",
        )
else:
    st.info("ยังไม่ได้นำเข้างบการเงินปีก่อน (สามารถข้ามได้หากใช้ยอด Prior Balance ใน TB หรือยังไม่มีงบปีก่อน)")

render_page_review_signoff("prior_year", lang)
