from __future__ import annotations

from datetime import datetime
import json
from typing import Any
import pandas as pd
import streamlit as st

from thai_accounting_audit_pack.src.models import ChangeLogEntry, EntitySetup, t


def init_session_state() -> None:
    """Initialize all Streamlit session state keys safely (Streamlit Cloud compatible, no local filesystem persistence)."""
    defaults: dict[str, Any] = {
        "entity_setup": EntitySetup().model_dump(),
        "tb_raw_name": "",
        "tb_raw_sheet": "",
        "tb_normalized": pd.DataFrame(),
        "gl_raw_name": "",
        "gl_raw_sheet": "",
        "gl_normalized": pd.DataFrame(),
        "prior_year_extracted": pd.DataFrame(),
        "prior_year_review": pd.DataFrame(),
        "prior_year_meta": {},
        "prior_year_mode": "Comparative Source",
        "dq_report": pd.DataFrame(),
        "dq_details": {},
        "coa_mapping": pd.DataFrame(),
        "grouping_version": "v1.0",
        "adjustments": pd.DataFrame(),
        "notes_index": pd.DataFrame(),
        "notes_draft": pd.DataFrame(),
        "risk_weights": {
            "materiality_ratio": 25,
            "period_fluctuation": 15,
            "management_override_or_manual": 15,
            "year_end_cutoff": 15,
            "related_party": 10,
            "accounting_complexity_or_estimate": 10,
            "evidence_gap_or_suspense": 10,
        },
        "auditor_opinion": "ยังไม่ระบุ — รอ CPA พิจารณา (ไม่สามารถสรุปความเห็นได้จากข้อมูลในระบบ)",
        "auditor_edits": {},
        "review_signoffs": {},
        "change_log": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_setup() -> EntitySetup:
    init_session_state()
    return EntitySetup(**st.session_state["entity_setup"])


def save_setup(setup: EntitySetup) -> None:
    st.session_state["entity_setup"] = setup.model_dump()


def log_change(module: str, action: str, target: str, old_value: str = "", new_value: str = "", note: str = "") -> None:
    init_session_state()
    entry = ChangeLogEntry(
        module=module,
        action=action,
        target=target,
        old_value=str(old_value),
        new_value=str(new_value),
        note=note,
    ).model_dump()
    st.session_state["change_log"].append(entry)


def export_session_config_json() -> bytes:
    """Export EntitySetup, Mapping, Adjustments, and Review Signoffs as JSON for Streamlit Cloud reload."""
    init_session_state()
    payload = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "entity_setup": st.session_state["entity_setup"],
        "coa_mapping": st.session_state["coa_mapping"].to_dict(orient="records") if not st.session_state["coa_mapping"].empty else [],
        "adjustments": st.session_state["adjustments"].to_dict(orient="records") if not st.session_state["adjustments"].empty else [],
        "prior_year_mode": st.session_state["prior_year_mode"],
        "risk_weights": st.session_state["risk_weights"],
        "auditor_opinion": st.session_state["auditor_opinion"],
        "auditor_edits": st.session_state["auditor_edits"],
        "review_signoffs": st.session_state["review_signoffs"],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def import_session_config_json(raw_bytes: bytes) -> None:
    data = json.loads(raw_bytes.decode("utf-8"))
    if "entity_setup" in data:
        st.session_state["entity_setup"] = EntitySetup(**data["entity_setup"]).model_dump()
    if data.get("coa_mapping"):
        st.session_state["coa_mapping"] = pd.DataFrame(data["coa_mapping"])
    if data.get("adjustments"):
        st.session_state["adjustments"] = pd.DataFrame(data["adjustments"])
    if "prior_year_mode" in data:
        st.session_state["prior_year_mode"] = data["prior_year_mode"]
    if "risk_weights" in data:
        st.session_state["risk_weights"] = data["risk_weights"]
    if "auditor_opinion" in data:
        st.session_state["auditor_opinion"] = data["auditor_opinion"]
    if "auditor_edits" in data:
        st.session_state["auditor_edits"] = data["auditor_edits"]
    if "review_signoffs" in data:
        st.session_state["review_signoffs"] = data["review_signoffs"]
    log_change("Session", "Import Config", "Session JSON", note="Restored configuration, mapping, and review status")


def render_sidebar_and_header(page_key: str, page_title_th: str, page_title_en: str) -> EntitySetup:
    """Render shared sidebar controls (Section 13) and consistent status banner on every page."""
    init_session_state()
    setup = get_setup()
    lang = setup.language

    with st.sidebar:
        st.markdown("### ⚙️ " + t(lang, "ตั้งค่าภาพรวม (Session)", "Global Session Controls"))
        lang_choice = st.radio(
            t(lang, "ภาษา / Language", "Language / ภาษา"),
            options=["th", "en"],
            index=0 if lang == "th" else 1,
            format_func=lambda x: "ไทย (TH)" if x == "th" else "English (EN)",
            horizontal=True,
        )
        if lang_choice != setup.language:
            setup.language = lang_choice
            save_setup(setup)
            st.rerun()

        st.text_input(t(lang, "บริษัท", "Entity"), value=setup.entity_name, disabled=True)
        st.text_input(t(lang, "วันสิ้นงวด", "Period End"), value=str(setup.period_end), disabled=True)
        st.text_input(t(lang, "กรอบมาตรฐาน", "Framework"), value=setup.framework, disabled=True)

        unit_opt = st.selectbox(
            t(lang, "หน่วยแสดงผล", "Display Unit"),
            options=["บาท", "พันบาท", "ล้านบาท"],
            index=["บาท", "พันบาท", "ล้านบาท"].index(setup.unit_scale),
        )
        mat_val = st.number_input(
            t(lang, "Materiality (บาท)", "Materiality (THB)"),
            min_value=1000.0,
            value=float(setup.materiality_amount),
            step=10000.0,
        )
        high_min = st.slider(
            t(lang, "เกณฑ์ Risk Level High >= ", "Risk Threshold (High >=)"),
            min_value=30,
            max_value=90,
            value=int(setup.risk_medium_max + 1),
        )
        if unit_opt != setup.unit_scale or mat_val != setup.materiality_amount or (high_min - 1) != setup.risk_medium_max:
            setup.unit_scale = unit_opt
            setup.materiality_amount = float(mat_val)
            setup.risk_medium_max = int(high_min - 1)
            save_setup(setup)

        st.divider()
        st.caption(
            t(
                lang,
                "☁️ Streamlit Cloud Notice: ข้อมูลประมวลผลใน Session เท่านั้น ไม่บันทึกถาวรบนเครื่อง กรุณาดาวน์โหลด Config JSON หรือ Excel Pack",
                "☁️ Streamlit Cloud Notice: Data stays in session memory only. Download Config JSON or Excel Pack to save progress.",
            )
        )
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.download_button(
                "💾 Config JSON",
                data=export_session_config_json(),
                file_name=f"session_config_{setup.period_end}.json",
                mime="application/json",
                use_container_width=True,
            )
        with col_s2:
            if st.button("🔄 Reset", use_container_width=True):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

        cfg_up = st.file_uploader(t(lang, "กู้คืน Config JSON", "Restore Config JSON"), type=["json"], key=f"restore_{page_key}")
        if cfg_up is not None:
            try:
                import_session_config_json(cfg_up.read())
                st.success("กู้คืน Config & Mapping สำเร็จ")
                st.rerun()
            except Exception as exc:
                st.error(f"ไม่สามารถอ่านไฟล์ JSON ได้: {exc}")

    # Page Title & Status Banner
    st.title(t(lang, page_title_th, page_title_en))
    tb_ok = not st.session_state["tb_normalized"].empty
    gl_ok = not st.session_state["gl_normalized"].empty
    dq = st.session_state["dq_report"]
    err_cnt = int((dq["Status"] == "Error").sum()) if not dq.empty else 0
    warn_cnt = int((dq["Status"] == "Warning").sum()) if not dq.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t(lang, "กรอบมาตรฐาน", "Framework"), setup.framework, "✅ Confirmed" if setup.framework_confirmed else "⚠️ รอยืนยัน")
    c2.metric(t(lang, "ความสมบูรณ์ข้อมูล", "Data Completeness"), f"TB: {'OK' if tb_ok else 'ไม่มี'} | GL: {'OK' if gl_ok else 'ไม่มี'}")
    c3.metric(t(lang, "Errors / Warnings", "Errors / Warnings"), f"{err_cnt} / {warn_cnt}")
    signoff_done = st.session_state["review_signoffs"].get(page_key, False)
    c4.metric(t(lang, "สถานะหน้านี้", "Page Review"), "✅ Reviewed" if signoff_done else "⏳ Pending Review")

    st.info(
        t(
            lang,
            "หมายเหตุวิชาชีพ: เอกสารและตัวเลขทั้งหมดเป็น **ฉบับร่างเพื่อการสอบทาน (Draft for Review)** ระบบไม่ส่งข้อมูลไปยังภายนอก และห้ามอ้างอิงว่าเป็นงบการเงินที่ตรวจสอบหรือลงนามแล้ว",
            "Professional Notice: All outputs are **Draft for Accountant/CPA Review**. No data is transmitted externally, and outputs do not constitute audited financial statements.",
        )
    )
    return setup


def render_page_review_signoff(page_key: str, lang: str) -> None:
    """Every page has a Mark as Reviewed button (Section 13)."""
    st.divider()
    reviewed = st.session_state["review_signoffs"].get(page_key, False)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(t(lang, "บันทึกสถานะการสอบทานหน้านี้ลงใน Change Log และ Session", "Record page review sign-off in Change Log"))
    with col2:
        label = "✅ Marked as Reviewed" if reviewed else "☑️ Mark as Reviewed"
        if st.button(label, key=f"btn_review_{page_key}", use_container_width=True):
            new_val = not reviewed
            st.session_state["review_signoffs"][page_key] = new_val
            log_change(page_key, "Page Review Sign-off", page_key, str(reviewed), str(new_val))
            st.rerun()
