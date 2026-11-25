from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config_loader import get_presentation_rules, get_reference_register
from src.models import t
from src.ui_helpers import log_change, render_page_review_signoff, render_sidebar_and_header, save_setup


st.set_page_config(page_title="00 Entity & Framework Setup", page_icon="🏢", layout="wide")
setup = render_sidebar_and_header(
    "setup",
    "00. ตั้งค่ากิจการ กรอบมาตรฐานบัญชี และแบบ DBD",
    "00. Entity & Reporting Framework Setup",
)
lang = setup.language

st.warning(
    t(
        lang,
        "ก่อนประมวลผลและจัดทำงบการเงินฉบับร่าง กรุณายืนยันกรอบการรายงานทางการเงิน ประเภทนิติบุคคล และข้อมูลประกอบด้านล่างให้ครบถ้วน (แบบรายการย่อ DBD เป็นเพียงรูปแบบการนำเสนอ ไม่ใช่มาตรฐานบัญชีหรือการรับรองการตรวจสอบ)",
        "Please confirm the financial reporting framework, entity type, and reporting parameters before generating financial statements.",
    )
)

with st.form("entity_setup_form"):
    c1, c2 = st.columns(2)
    with c1:
        entity_name = st.text_input("ชื่อนิติบุคคล (Entity Name) *", value=setup.entity_name)
        reg_no = st.text_input("เลขทะเบียนนิติบุคคล (13 หลัก - ถ้ามี)", value=setup.registration_no)
        entity_type = st.selectbox(
            "ประเภทนิติบุคคล *",
            options=["บริษัทจำกัด", "บริษัทมหาชนจำกัด", "ห้างหุ้นส่วนจดทะเบียน", "นิติบุคคลประเภทอื่น"],
            index=["บริษัทจำกัด", "บริษัทมหาชนจำกัด", "ห้างหุ้นส่วนจดทะเบียน", "นิติบุคคลประเภทอื่น"].index(setup.entity_type),
        )
        custom_entity_type = st.text_input("ระบุประเภทนิติบุคคลอื่น (กรณีเลือก 'นิติบุคคลประเภทอื่น')", value=setup.custom_entity_type)
        business_type = st.text_input("ประเภทธุรกิจหลัก *", value=setup.business_type)

    with c2:
        framework_opts = [
            "TFRS for NPAEs",
            "TFRS for PAEs / TFRS เต็มรูปแบบ",
            "TFRS อื่นที่ผู้ใช้กำหนด",
            "กรอบภายในหรือ Management Reporting",
        ]
        framework = st.selectbox("Financial Reporting Framework *", options=framework_opts, index=framework_opts.index(setup.framework))
        custom_fw = st.text_input("ชื่อกรอบ/มาตรฐานที่กำหนดเอง (ถ้าเลือกกรอบอื่น)", value=setup.custom_framework_name)
        custom_src = st.text_input("แหล่งอ้างอิงและปีของมาตรฐาน (ถ้ากำหนดเอง)", value=f"{setup.custom_framework_source} {setup.custom_framework_year}".strip())
        dbd_templates = [
            "แบบ 2 บริษัทจำกัด (ประกาศฯ พ.ศ. 2566)",
            "แบบ 3 บริษัทมหาชนจำกัด (ประกาศฯ พ.ศ. 2566)",
            "แบบ 1 ห้างหุ้นส่วนจดทะเบียน (ประกาศฯ พ.ศ. 2566)",
            "กำหนดเอง / อัปโหลดแบบ DBD เพิ่มเติม",
        ]
        dbd_idx = dbd_templates.index(setup.dbd_template) if setup.dbd_template in dbd_templates else 0
        dbd_template = st.selectbox("DBD Presentation Template", options=dbd_templates, index=dbd_idx)
        audit_std_ref = st.text_input("Audit Report Framework (มาตรฐานการสอบบัญชีและปี)", value=setup.audit_standard_ref)

    st.subheader("รอบระยะเวลาบัญชีและทางเลือกการนำเสนอ")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        period_start = st.date_input("วันเริ่มรอบบัญชี", value=setup.period_start)
    with p2:
        period_end = st.date_input("วันสิ้นงวดบัญชี", value=setup.period_end)
    with p3:
        comp_label = st.text_input("งวดเปรียบเทียบ", value=setup.comparative_period_label)
    with p4:
        currency = st.text_input("สกุลเงินหลัก", value=setup.currency)

    o1, o2, o3 = st.columns(3)
    with o1:
        exp_pres = st.selectbox(
            "วิธีนำเสนอค่าใช้จ่าย",
            options=["ตามหน้าที่ (Function)", "ตามธรรมชาติ (Nature)"],
            index=0 if setup.expense_presentation.startswith("ตามหน้าที่") else 1,
        )
    with o2:
        cf_method = st.selectbox(
            "วิธีจัดทำงบกระแสเงินสด",
            options=["ทางอ้อม (Indirect)", "ทางตรง (Direct)"],
            index=0 if setup.cashflow_method.startswith("ทางอ้อม") else 1,
        )
    with o3:
        prepare_cf = st.checkbox("จัดทำงบกระแสเงินสด", value=setup.prepare_cashflow)

    st.subheader("ขอบเขตรายการสำคัญและสถานะกิจการ (Section 1.2 & B)")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        is_listed = st.checkbox("จดทะเบียนในตลาดหลักทรัพย์", value=setup.is_listed)
        has_subs = st.checkbox("มีบริษัทย่อย/บริษัทร่วม", value=setup.has_subsidiaries)
        has_rp = st.checkbox("มีบุคคล/กิจการที่เกี่ยวข้องกัน", value=setup.has_related_parties)
    with f2:
        dbd_req = st.checkbox("มีหน้าที่นำส่งงบต่อ DBD", value=setup.dbd_filing_required)
        has_inv = st.checkbox("มีสินค้าคงเหลือ", value=setup.has_inventory)
        has_ar = st.checkbox("มีลูกหนี้การค้า/ลูกหนี้อื่น", value=setup.has_receivables)
    with f3:
        has_ppe = st.checkbox("มีสินทรัพย์ถาวร (PPE)", value=setup.has_ppe)
        has_lease = st.checkbox("มีสัญญาเช่า", value=setup.has_leases)
        has_loan = st.checkbox("มีเงินกู้ยืม", value=setup.has_borrowings)
    with f4:
        has_tax = st.checkbox("มีภาษีเงินได้", value=setup.has_income_tax)
        has_est = st.checkbox("มีประมาณการทางบัญชีสำคัญ", value=setup.has_significant_estimates)
        fw_confirm = st.checkbox("ยืนยันความถูกต้องของกรอบมาตรฐานและข้อมูลกิจการ *", value=setup.framework_confirmed)

    submitted = st.form_submit_button("💾 บันทึกและยืนยันการตั้งค่า", type="primary")
    if submitted:
        setup.entity_name = entity_name.strip()
        setup.registration_no = reg_no.strip()
        setup.entity_type = entity_type
        setup.custom_entity_type = custom_entity_type.strip()
        setup.business_type = business_type.strip()
        setup.framework = framework
        setup.custom_framework_name = custom_fw.strip()
        setup.custom_framework_source = custom_src.strip()
        setup.dbd_template = dbd_template
        setup.audit_standard_ref = audit_std_ref.strip()
        setup.period_start = period_start
        setup.period_end = period_end
        setup.comparative_period_label = comp_label.strip()
        setup.currency = currency.strip() or "THB"
        setup.expense_presentation = exp_pres
        setup.cashflow_method = cf_method
        setup.prepare_cashflow = prepare_cf
        setup.is_listed = is_listed
        setup.has_subsidiaries = has_subs
        setup.has_related_parties = has_rp
        setup.dbd_filing_required = dbd_req
        setup.has_inventory = has_inv
        setup.has_receivables = has_ar
        setup.has_ppe = has_ppe
        setup.has_leases = has_lease
        setup.has_borrowings = has_loan
        setup.has_income_tax = has_tax
        setup.has_significant_estimates = has_est
        setup.framework_confirmed = fw_confirm
        save_setup(setup)
        log_change("Entity Setup", "Update Setup", setup.entity_name, new_value=f"{setup.framework} / {setup.dbd_template}")
        st.success("บันทึกการตั้งค่าเรียบร้อยแล้ว!")
        st.rerun()

st.subheader("การแยกชั้นข้อมูลตามมาตรฐานและกฎหมาย (Presentation Separation)")
sep_df = pd.DataFrame(
    [
        {"Layer": "Financial Reporting Framework", "Selected": setup.framework, "Purpose": "กำหนดหลักการรับรู้ วัดมูลค่า และเปิดเผยข้อมูลทางบัญชี"},
        {"Layer": "DBD Presentation Template", "Selected": setup.dbd_template, "Purpose": "รูปแบบรายการย่อเพื่อนำส่งต่อกรมพัฒนาธุรกิจการค้า (ไม่ใช่มาตรฐานบัญชี)"},
        {"Layer": "Audit Report Framework", "Selected": setup.audit_standard_ref, "Purpose": "มาตรฐานการสอบบัญชีสำหรับร่างรายงานผู้สอบบัญชีรับอนุญาต (Draft for CPA Review)"},
        {"Layer": "Management View", "Selected": f"{setup.currency} ({setup.unit_scale})", "Purpose": "Dashboard วิเคราะห์ผู้บริหาร ปิดบัญชี และเตรียมความพร้อมตรวจ"},
    ]
)
st.dataframe(sep_df, use_container_width=True, hide_index=True)

with st.expander("📚 ดู Reference Register (TFAC & DBD Official Links)"):
    reg = get_reference_register()
    st.dataframe(pd.DataFrame(reg.get("tfac_standards", []) + reg.get("dbd_references", [])), use_container_width=True, hide_index=True)

with st.expander("📋 อัปโหลดแบบรายการย่อ DBD เพิ่มเติม (กรณีไม่สามารถเข้าถึงไฟล์จากเว็บไซต์ DBD โดยตรง)"):
    dbd_up = st.file_uploader("แนบไฟล์ประกาศ/แบบรายการย่อ DBD (PDF/XLSX)", type=["pdf", "xlsx"])
    if dbd_up is not None:
        st.session_state["custom_dbd_doc_name"] = dbd_up.name
        log_change("Entity Setup", "Upload Custom DBD Reference", dbd_up.name)
        st.success(f"บันทึกเอกสารอ้างอิง DBD: {dbd_up.name} ใน Session แล้ว")

render_page_review_signoff("setup", lang)
