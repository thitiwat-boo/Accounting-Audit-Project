from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

from thai_accounting_audit_pack.src.accounting_rules import compute_adjusted_tb, generate_proposed_adjustments
from thai_accounting_audit_pack.src.config_loader import SAMPLE_DIR, get_reference_register
from thai_accounting_audit_pack.src.loaders import auto_detect_columns, GL_COLUMN_SYNONYMS, normalize_gl, normalize_tb, TB_COLUMN_SYNONYMS
from thai_accounting_audit_pack.src.mapping import build_initial_coa_mapping
from thai_accounting_audit_pack.src.models import t
from thai_accounting_audit_pack.src.ui_helpers import init_session_state, log_change, render_page_review_signoff, render_sidebar_and_header, save_setup
from thai_accounting_audit_pack.src.validators import run_data_quality_checks


st.set_page_config(
    page_title="Thai Accounting, FS & Audit Workpaper Pack",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

setup = render_sidebar_and_header(
    "home",
    "ระบบจัดเตรียมงบการเงิน กระดาษทำการสอบบัญชี และ Management Dashboard",
    "Accounting, Financial Statements, Audit Workpaper & Management Dashboard",
)
lang = setup.language

st.markdown(
    t(
        lang,
        """
### ขั้นตอนการทำงาน (Workflow ตามมาตรฐานวิชาชีพบัญชีและสอบบัญชี)
1. **Entity & Framework Setup (`00`)**: ยืนยันกรอบมาตรฐาน (TFRS for NPAEs / PAEs / Custom), ประเภทนิติบุคคล และแบบรายการย่อ DBD
2. **นำเข้าข้อมูล TB/GL (`01`)**: อัปโหลดไฟล์ Excel `.xlsx` แยก TB และ GL พร้อมเลือก Sheet และ Map คอลัมน์เองได้ หรือโหลดข้อมูลตัวอย่าง
3. **นำเข้างบการเงินปีก่อน (`02`)**: อัปโหลดงบปีก่อน (`.xlsx` / `.pdf`) พร้อมตรวจสอบ entity, เปรียบเทียบ opening balance และยืนยันยอดเปรียบเทียบ
4. **ตรวจสอบข้อมูล (`03`)**: Data Quality Report 14 รายการ (`Pass` / `Warning` / `Error`) พร้อมดูแถวต้นทาง
5. **ผังบัญชีและ Mapping (`04`)**: Mapping Wizard 5 ระดับ (`AI Suggested` / `Rule Based` / `User Confirmed`) — ห้ามออกงบ Final หากยังไม่ยืนยัน
6. **Adjusting Entries (`05`)**: บันทึกรายการปรับปรุงหรืออนุมัติ Proposed Adjustments โดยไม่แก้ TB ต้นฉบับ
7. **Financial Statements (`06`)**: งบแสดงฐานะการเงิน งบกำไรขาดทุน งบเปลี่ยนแปลงส่วนของเจ้าของ และงบกระแสเงินสด พร้อมปุ่ม `Show Formula` และ `Show Source`
8. **Notes to FS (`07`)**: Disclosure Checklist 23+ หมวด และร่างหมายเหตุพร้อม `[รอข้อมูลจากฝ่ายบริหาร]`
9. **Audit Workpaper (`08`)**: Revenue/Expense Review, Risk Scoring, Audit Workpaper 22 คอลัมน์, Confirmation และ Tax Check
10. **Draft Auditor's Report (`09`)**: ร่างรายงานผู้สอบบัญชี (`Draft for CPA Review`) ที่ไม่เลือกความเห็นหรือใส่เลขทะเบียน CPA เอง
11. **Management Dashboard (`10`)**: 3 มุมมอง (Executive / Accounting Close / Audit Readiness) พร้อมปุ่ม `View calculation`
12. **Reconciliation & Sign-off (`11`) & Export (`12`)**: กระทบยอดทุกงบและส่งออก Excel Pack 50+ Sheets พร้อมสูตรจริงและ `Formula_Check`
""",
        """
### End-to-End Accounting & Audit Preparation Workflow
Use the left sidebar navigation (`00` through `12`) to configure the reporting framework, import TB/GL and prior-year FS, validate data quality, confirm 5-level COA mapping, review adjusting entries, inspect formula-driven financial statements, draft notes and audit workpapers, review executive dashboards, and export the full multi-sheet Excel Audit Pack.
""",
    )
)

st.divider()
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader(t(lang, "เริ่มต้นอย่างรวดเร็วด้วยข้อมูลตัวอย่าง (Quick Start Sample Data)", "Quick Start with Sample TB/GL"))
    st.caption(
        t(
            lang,
            "ปุ่มนี้จะโหลดไฟล์ตัวอย่างจากโฟลเดอร์ `sample_data/` ของโปรเจกต์เข้าสู่ Session เพื่อทดสอบระบบครบทุกขั้นตอน (ตัวเลขไม่ได้ hard-code ในโค้ด แต่โหลดจากไฟล์ Excel จริง)",
            "Loads real sample Excel files from `sample_data/` into your session so you can test the full pipeline.",
        )
    )
    if st.button("🚀 " + t(lang, "โหลด Sample TB + Sample GL เข้า Session", "Load Sample TB + Sample GL"), type="primary"):
        tb_path = SAMPLE_DIR / "sample_tb.xlsx"
        gl_path = SAMPLE_DIR / "sample_gl.xlsx"
        if tb_path.exists() and gl_path.exists():
            raw_tb = pd.read_excel(tb_path, sheet_name="Trial_Balance", dtype=object)
            raw_gl = pd.read_excel(gl_path, sheet_name="General_Ledger", dtype=object)
            tb_map = auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS)
            gl_map = auto_detect_columns(list(raw_gl.columns), GL_COLUMN_SYNONYMS)
            tb_norm, _ = normalize_tb(raw_tb, tb_map, "sample_tb.xlsx", "Trial_Balance", 1)
            gl_norm, _ = normalize_gl(raw_gl, gl_map, "sample_gl.xlsx", "General_Ledger", 1)
            st.session_state["tb_raw_name"] = "sample_tb.xlsx"
            st.session_state["tb_raw_sheet"] = "Trial_Balance"
            st.session_state["tb_normalized"] = tb_norm
            st.session_state["gl_raw_name"] = "sample_gl.xlsx"
            st.session_state["gl_raw_sheet"] = "General_Ledger"
            st.session_state["gl_normalized"] = gl_norm
            dq_df, dq_det = run_data_quality_checks(tb_norm, gl_norm, setup.period_start, setup.period_end)
            st.session_state["dq_report"] = dq_df
            st.session_state["dq_details"] = dq_det
            coa_map = build_initial_coa_mapping(tb_norm, gl_norm, setup.materiality_amount)
            st.session_state["coa_mapping"] = coa_map
            st.session_state["adjustments"] = generate_proposed_adjustments(tb_norm, gl_norm, coa_map, setup.period_end)
            setup.framework_confirmed = True
            save_setup(setup)
            log_change("Home", "Load Sample Data", "sample_tb.xlsx + sample_gl.xlsx", note="Loaded real Excel sample files")
            st.success("โหลดข้อมูลตัวอย่างสำเร็จ! สามารถเปิดดูหน้า 03–12 ได้ทันที")
            st.rerun()
        else:
            st.error("ไม่พบไฟล์ใน sample_data/ กรุณารัน scripts/generate_samples.py ก่อน")

with col2:
    st.subheader(t(lang, "แหล่งอ้างอิงทางการ (TFAC / DBD)", "Official References (TFAC / DBD)"))
    reg = get_reference_register()
    for item in (reg.get("tfac_standards", [])[:3] + reg.get("dbd_references", [])[:2]):
        st.markdown(f"- [{item['title']}]({item['url']}) (`{item['version']}`)")

render_page_review_signoff("home", lang)
