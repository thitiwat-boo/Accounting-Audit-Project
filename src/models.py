from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class EntitySetup(BaseModel):
    """ข้อมูลกิจการและกรอบการรายงานทางการเงินที่ผู้ใช้ยืนยันก่อนประมวลผล"""

    entity_name: str = "บริษัท ตัวอย่าง การค้า จำกัด"
    registration_no: str = ""
    entity_type: Literal[
        "บริษัทจำกัด",
        "บริษัทมหาชนจำกัด",
        "ห้างหุ้นส่วนจดทะเบียน",
        "นิติบุคคลประเภทอื่น",
    ] = "บริษัทจำกัด"
    custom_entity_type: str = ""
    business_type: str = "ซื้อมาขายไปและให้บริการ"

    # Framework & Standard Confirmation (Section 1.1 & Addendum B)
    framework: Literal[
        "TFRS for NPAEs",
        "TFRS for PAEs / TFRS เต็มรูปแบบ",
        "TFRS อื่นที่ผู้ใช้กำหนด",
        "กรอบภายในหรือ Management Reporting",
    ] = "TFRS for NPAEs"
    custom_framework_name: str = ""
    custom_framework_source: str = ""
    custom_framework_year: str = ""
    framework_confirmed: bool = False

    # Period & Comparative
    period_start: date = date(2025, 1, 1)
    period_end: date = date(2025, 12, 31)
    comparative_period_label: str = "2024"
    has_comparative: bool = True

    # Presentation & Filing
    currency: str = "THB"
    unit_scale: Literal["บาท", "พันบาท", "ล้านบาท"] = "บาท"
    language: Literal["th", "en"] = "th"
    expense_presentation: Literal["ตามหน้าที่ (Function)", "ตามธรรมชาติ (Nature)"] = "ตามหน้าที่ (Function)"
    cashflow_method: Literal["ทางอ้อม (Indirect)", "ทางตรง (Direct)"] = "ทางตรง (Direct)" if False else "ทางอ้อม (Indirect)"
    prepare_cashflow: bool = True
    is_listed: bool = False
    has_subsidiaries: bool = False
    has_related_parties: bool = True
    dbd_filing_required: bool = True
    dbd_template: str = "แบบ 2 บริษัทจำกัด (ประกาศฯ พ.ศ. 2566)"

    # Key Accounting Areas Checklist (Section 1.2)
    has_inventory: bool = True
    has_receivables: bool = True
    has_ppe: bool = True
    has_leases: bool = True
    has_borrowings: bool = True
    has_income_tax: bool = True
    has_significant_estimates: bool = True

    # Audit & Materiality Settings
    materiality_amount: float = 100_000.0
    performance_materiality_pct: float = 0.75
    trivial_threshold_pct: float = 0.05
    risk_low_max: int = 29
    risk_medium_max: int = 54
    risk_high_max: int = 79

    # Audit Standard Reference
    audit_standard_ref: str = "TSA 700 (ปรับปรุง) - สภาวิชาชีพบัญชี (2563)"
    audit_standard_year: str = "2563"

    @property
    def unit_divisor(self) -> float:
        if self.unit_scale == "พันบาท":
            return 1_000.0
        if self.unit_scale == "ล้านบาท":
            return 1_000_000.0
        return 1.0

    @property
    def effective_entity_type(self) -> str:
        if self.entity_type == "นิติบุคคลประเภทอื่น" and self.custom_entity_type.strip():
            return self.custom_entity_type.strip()
        return self.entity_type


class CellFormulaRecord(BaseModel):
    """Metadata ระดับเซลล์สำหรับ Cell_Formula_Map และ Source_Traceability"""

    output_file: str
    output_sheet: str
    output_cell: str
    formula: str
    displayed_value: Any
    source_sheet: str
    source_cell_or_row: str
    source_account_code: str = ""
    source_gl_reference: str = ""
    adjustment_reference: str = ""
    mapping_reference: str = ""
    calculation_description: str = ""
    review_status: str = "Formula Generated / Review Required"


class ChangeLogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    user: str = "Current User"
    module: str
    action: str
    target: str
    old_value: str = ""
    new_value: str = ""
    note: str = ""


def t(lang: str, th: str, en: str) -> str:
    """Simple bilingual helper returning Thai or English text."""
    return th if lang == "th" else en


def get_default_sidebar_labels(lang: str) -> dict[str, str]:
    return {
        "entity": t(lang, "กิจการ", "Entity"),
        "period": t(lang, "วันสิ้นงวด", "Period End"),
        "standard": t(lang, "กรอบมาตรฐาน", "Framework"),
        "currency": t(lang, "สกุลเงิน/หน่วย", "Currency / Unit"),
        "materiality": t(lang, "ความมีสาระสำคัญ (Materiality)", "Materiality"),
        "risk_threshold": t(lang, "เกณฑ์ความเสี่ยง (High >=)", "Risk Threshold (High >=)"),
        "reset": t(lang, "รีเซ็ตเซสชัน", "Reset Session"),
        "export": t(lang, "ส่งออก Excel Pack", "Export Excel Pack"),
    }
