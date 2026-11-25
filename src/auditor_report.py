from __future__ import annotations

from typing import Any
import pandas as pd

from src.config_loader import get_reference_register
from src.models import EntitySetup


OPINION_CHOICES = [
    "ยังไม่ระบุ — รอ CPA พิจารณา (ไม่สามารถสรุปความเห็นได้จากข้อมูลในระบบ)",
    "ความเห็นอย่างไม่มีเงื่อนไข (Unmodified / Unqualified Opinion - ร่างสำหรับ CPA)",
    "ความเห็นอย่างมีเงื่อนไข (Qualified Opinion - ร่างสำหรับ CPA)",
    "ความเห็นว่างบการเงินไม่ถูกต้อง (Adverse Opinion - ร่างสำหรับ CPA)",
    "ไม่แสดงความเห็น (Disclaimer of Opinion - ร่างสำหรับ CPA)",
]


def collect_unresolved_issues(
    dq_df: pd.DataFrame,
    unmapped_df: pd.DataFrame,
    adjustments_df: pd.DataFrame,
    fs_result: dict[str, Any],
    notes_index_df: pd.DataFrame,
) -> list[str]:
    """Identify unresolved gaps / scope limitations preventing unmodified opinion conclusion."""
    issues: list[str] = []
    if dq_df is not None and not dq_df.empty:
        errs = dq_df[dq_df["Status"] == "Error"]
        if not errs.empty:
            issues.append(f"พบข้อผิดพลาด Data Quality ระดับ Error จำนวน {len(errs)} รายการ: {', '.join(errs['Check_Name'].tolist())}")
    if unmapped_df is not None and not unmapped_df.empty:
        issues.append(f"มีบัญชีที่ยังไม่ยืนยัน Mapping / บัญชีพักจำนวน {len(unmapped_df)} บัญชี")
    if adjustments_df is not None and not adjustments_df.empty:
        pending = adjustments_df[adjustments_df["Status"].isin(["Draft", "Proposed"])]
        if not pending.empty:
            issues.append(f"มีรายการปรับปรุงทางบัญชีรออนุมัติ (Draft/Proposed) จำนวน {len(pending)} รายการ")
    rec = fs_result.get("reconciliations", {}) if fs_result else {}
    if abs(float(rec.get("bs_balance_diff", 0.0))) > 0.01:
        issues.append(f"งบแสดงฐานะการเงินยังมีผลต่างสมดุล {rec.get('bs_balance_diff', 0.0):,.2f}")
    if notes_index_df is not None and not notes_index_df.empty:
        req_mgmt = notes_index_df[notes_index_df["Status"].isin(["Requires management input", "Requires supporting schedule"])]
        if not req_mgmt.empty:
            issues.append(f"หมายเหตุประกอบงบการเงินยังรอข้อมูลจากฝ่ายบริหาร/เอกสารประกอบจำนวน {len(req_mgmt)} ข้อ")
    issues.append("หลักฐานจาก TB และ GL เพียงอย่างเดียวไม่เพียงพอต่อการแสดงความเห็นสอบบัญชี (ต้องตรวจ Bank/AR/AP Confirmation, Stock Count และ Subsequent Events)")
    return issues


def build_draft_auditor_report(
    setup: EntitySetup,
    unresolved_issues: list[str],
    selected_opinion: str = OPINION_CHOICES[0],
    include_kam: bool = False,
    include_going_concern: bool = False,
    include_other_info: bool = False,
    cpa_custom_edits: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate Draft for CPA Review Auditor Report & Reference Table (Section 10 & G).
    Never auto-selects opinion and never fabricates CPA name, license number, or signature date.
    """
    edits = cpa_custom_edits or {}
    addressee = "ผู้เป็นหุ้นส่วน" if setup.entity_type == "ห้างหุ้นส่วนจดทะเบียน" else "ผู้ถือหุ้น"
    fw_label = (
        setup.custom_framework_name
        if setup.framework == "TFRS อื่นที่ผู้ใช้กำหนด" and setup.custom_framework_name
        else setup.framework
    )
    is_pae = setup.framework == "TFRS for PAEs / TFRS เต็มรูปแบบ" or setup.entity_type == "บริษัทมหาชนจำกัด"
    stmts_list = (
        "งบแสดงฐานะการเงิน งบกำไรขาดทุนเบ็ดเสร็จ งบแสดงการเปลี่ยนแปลงส่วนของผู้ถือหุ้น และงบกระแสเงินสด"
        if is_pae
        else "งบแสดงฐานะการเงิน งบกำไรขาดทุน และงบแสดงการเปลี่ยนแปลงส่วนของเจ้าของ/ผู้ถือหุ้น"
    )

    insufficient_notice = (
        "ไม่สามารถสรุปความเห็นได้จากข้อมูลในระบบ (TB/GL เพียงอย่างเดียวไม่เพียงพอสำหรับการแสดงความเห็นของผู้สอบบัญชีรับอนุญาต) "
        if selected_opinion == OPINION_CHOICES[0]
        else selected_opinion
    )

    paragraphs: list[dict[str, Any]] = [
        {
            "Paragraph_ID": "AR-00",
            "Paragraph_Type": "Banner / สถานะเอกสาร",
            "Template_Source": "System Governance Rule (Section 10 & G)",
            "Applicable_Standard": setup.audit_standard_ref,
            "Entity_Type": setup.effective_entity_type,
            "Framework": fw_label,
            "Required_Inputs": "ยืนยันโดย CPA ผู้สอบทาน",
            "Generated_Text": "DRAFT FOR CPA REVIEW ONLY — เอกสารฉบับร่างเพื่อประกอบการสอบทานโดยผู้สอบบัญชีรับอนุญาต ห้ามถือเป็นรายงานที่ตรวจสอบและลงนามแล้ว",
        },
        {
            "Paragraph_ID": "AR-01",
            "Paragraph_Type": "ชื่อรายงานและผู้รับรายงาน",
            "Template_Source": f"TSA 700 (ปรับปรุง) / รูปแบบนิติบุคคล ({setup.dbd_template})",
            "Applicable_Standard": setup.audit_standard_ref,
            "Entity_Type": setup.effective_entity_type,
            "Framework": fw_label,
            "Required_Inputs": "ชื่อนิติบุคคล, ประเภทกิจการ",
            "Generated_Text": f"รายงานของผู้สอบบัญชีรับอนุญาต (ฉบับร่าง)\nเสนอต่อ {addressee}ของ {setup.entity_name}",
        },
        {
            "Paragraph_ID": "AR-02",
            "Paragraph_Type": "ความเห็น (Opinion - ร่าง)",
            "Template_Source": "TSA 700 (ปรับปรุง) ย่อหน้า 23-28",
            "Applicable_Standard": setup.audit_standard_ref,
            "Entity_Type": setup.effective_entity_type,
            "Framework": fw_label,
            "Required_Inputs": "ประเภทความเห็นที่ CPA เลือกด้วยตนเอง, วันสิ้นงวด",
            "Generated_Text": (
                f"[สถานะการเลือกความเห็นโดย CPA: {insufficient_notice}]\n"
                f"งบการเงินฉบับร่างที่นำมาประกอบการสอบทานของ {setup.entity_name} ประกอบด้วย {stmts_list} "
                f"สำหรับรอบระยะเวลาบัญชีสิ้นสุดวันที่ {setup.period_end} และหมายเหตุประกอบงบการเงิน\n"
                f"[รอ CPA กรอกถ้อยคำความเห็นขั้นสุดท้ายหลังการรวบรวมหลักฐานการสอบบัญชีครบถ้วน]"
            ),
        },
        {
            "Paragraph_ID": "AR-03",
            "Paragraph_Type": "เกณฑ์ในการแสดงความเห็น (Basis for Opinion)",
            "Template_Source": "TSA 700 (ปรับปรุง) ย่อหน้า 28",
            "Applicable_Standard": setup.audit_standard_ref,
            "Entity_Type": setup.effective_entity_type,
            "Framework": fw_label,
            "Required_Inputs": "รายการ Unresolved Issues / ขอบเขตที่ยังขาดหลักฐาน",
            "Generated_Text": (
                f"การตรวจสอบต้องปฏิบัติตามมาตรฐานการสอบบัญชี ({setup.audit_standard_ref}) และข้อกำหนดจรรยาบรรณของผู้ประกอบวิชาชีพบัญชี\n"
                "ประเด็นที่ยังไม่แล้วเสร็จ/หลักฐานที่ยังต้องรวบรวมเพิ่มเติมในระบบ:\n- "
                + "\n- ".join(unresolved_issues)
            ),
        },
        {
            "Paragraph_ID": "AR-04",
            "Paragraph_Type": "ความรับผิดชอบของผู้บริหารต่องบการเงิน",
            "Template_Source": "TSA 700 (ปรับปรุง) ย่อหน้า 33-36",
            "Applicable_Standard": setup.audit_standard_ref,
            "Entity_Type": setup.effective_entity_type,
            "Framework": fw_label,
            "Required_Inputs": "กรอบการรายงานทางการเงินที่ใช้",
            "Generated_Text": (
                f"ผู้บริหารมีหน้าที่รับผิดชอบในการจัดทำและนำเสนองบการเงินเหล่านี้โดยถูกต้องตามที่ควรตาม {fw_label} "
                "และรับผิดชอบเกี่ยวกับการควบคุมภายในที่ผู้บริหารพิจารณาว่าจำเป็นเพื่อให้สามารถจัดทำงบการเงินที่ปราศจากการแสดงข้อมูลที่ขัดต่อข้อเท็จจริงอันเป็นสาระสำคัญ"
            ),
        },
        {
            "Paragraph_ID": "AR-05",
            "Paragraph_Type": "ความรับผิดชอบของผู้สอบบัญชีต่อการตรวจสอบงบการเงิน",
            "Template_Source": "TSA 700 (ปรับปรุง) ย่อหน้า 37-40",
            "Applicable_Standard": setup.audit_standard_ref,
            "Entity_Type": setup.effective_entity_type,
            "Framework": fw_label,
            "Required_Inputs": "มาตรฐานการสอบบัญชี",
            "Generated_Text": (
                "วัตถุประสงค์ของผู้สอบบัญชีคือการได้รับความเชื่อมั่นอย่างสมเหตุสมผลว่างบการเงินโดยรวมปราศจากการแสดงข้อมูลที่ขัดต่อข้อเท็จจริงอันเป็นสาระสำคัญหรือไม่ "
                "ทั้งนี้ความเชื่อมั่นอย่างสมเหตุสมผลไม่ใช่การรับประกันว่าการตรวจสอบตามมาตรฐานการสอบบัญชีจะสามารถตรวจพบข้อผิดพลาดอันเป็นสาระสำคัญได้เสมอไป"
            ),
        },
    ]

    if include_going_concern:
        paragraphs.append(
            {
                "Paragraph_ID": "AR-06",
                "Paragraph_Type": "ความไม่แน่นอนที่มีสาระสำคัญเกี่ยวกับการดำเนินงานต่อเนื่อง",
                "Template_Source": "TSA 570 (ปรับปรุง)",
                "Applicable_Standard": "TSA 570 (ปรับปรุง)",
                "Entity_Type": setup.effective_entity_type,
                "Framework": fw_label,
                "Required_Inputs": "หมายเหตุข้อ 21 และประมาณการกระแสเงินสด",
                "Generated_Text": "[ร่างสำหรับ CPA พิจารณาตาม TSA 570: อ้างอิงหมายเหตุประกอบงบการเงินข้อ 21 เกี่ยวกับความสามารถในการดำเนินงานต่อเนื่อง — รอหลักฐานและการประเมินจากผู้บริหาร]",
            }
        )
    if include_kam:
        paragraphs.append(
            {
                "Paragraph_ID": "AR-07",
                "Paragraph_Type": "เรื่องสำคัญในการตรวจสอบ (Key Audit Matters - KAM)",
                "Template_Source": "TSA 701",
                "Applicable_Standard": "TSA 701 (เฉพาะกิจการที่มีส่วนได้เสียสาธารณะ/เข้าเกณฑ์)",
                "Entity_Type": setup.effective_entity_type,
                "Framework": fw_label,
                "Required_Inputs": "เรื่องที่มีความเสี่ยงสูงหรือใช้ดุลยพินิจสำคัญที่ CPA สื่อสารกับผู้มีหน้าที่ในการกำกับดูแล",
                "Generated_Text": "[ร่างสำหรับ CPA กรอกรายละเอียดเรื่องสำคัญในการตรวจสอบ (KAM) พร้อมวิธีตอบสนองความเสี่ยง]",
            }
        )
    if include_other_info:
        paragraphs.append(
            {
                "Paragraph_ID": "AR-08",
                "Paragraph_Type": "ข้อมูลอื่น (Other Information)",
                "Template_Source": "TSA 720 (ปรับปรุง)",
                "Applicable_Standard": "TSA 720 (ปรับปรุง)",
                "Entity_Type": setup.effective_entity_type,
                "Framework": fw_label,
                "Required_Inputs": "รายงานประจำปี / รายงานผู้บริหาร",
                "Generated_Text": "[ร่างสำหรับ CPA พิจารณาตาม TSA 720 หากกิจการมีการจัดทำรายงานประจำปีหรือข้อมูลอื่นที่แนบมากับงบการเงิน]",
            }
        )

    paragraphs.append(
        {
            "Paragraph_ID": "AR-99",
            "Paragraph_Type": "ลายมือชื่อ เลขทะเบียน ที่อยู่ และวันที่",
            "Template_Source": "TSA 700 (ปรับปรุง) ย่อหน้า 46-49",
            "Applicable_Standard": setup.audit_standard_ref,
            "Entity_Type": setup.effective_entity_type,
            "Framework": fw_label,
            "Required_Inputs": "ชื่อ CPA, เลขทะเบียนผู้สอบบัญชีรับอนุญาต, สำนักงานสอบบัญชี, วันที่ออกรายงาน",
            "Generated_Text": (
                "ลงชื่อ .................................................... (ห้ามระบบสร้างชื่อหรือเลขทะเบียนเอง)\n"
                "( [รอระบุชื่อผู้สอบบัญชีรับอนุญาต] )\n"
                "ผู้สอบบัญชีรับอนุญาต เลขทะเบียน [รอระบุเลขทะเบียน CPA]\n"
                "สำนักงาน/ที่อยู่: [รอระบุที่อยู่สำนักงาน]\n"
                "วันที่: [รอวันที่อนุมัติงบการเงินและออกรายงาน]"
            ),
        }
    )

    for p in paragraphs:
        pid = p["Paragraph_ID"]
        p["CPA_Edit"] = edits.get(pid, "")
        p["Approval_Status"] = "Draft for CPA Review"

    reg = get_reference_register()
    ref_rows = []
    for item in reg.get("tfac_standards", []) + reg.get("dbd_references", []):
        ref_rows.append(
            {
                "Ref_ID": item["id"],
                "Category": item["category"],
                "Document_Title": item["title"],
                "Issuer": item["issuer"],
                "Version": item["version"],
                "URL": item["url"],
                "Verified_Date": item["verified_date"],
            }
        )

    return pd.DataFrame(paragraphs), pd.DataFrame(ref_rows)
