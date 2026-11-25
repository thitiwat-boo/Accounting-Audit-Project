from __future__ import annotations

from typing import Any
import pandas as pd

from src.models import EntitySetup
from src.risk_scoring import score_risk_level


REVIEW_COLUMNS = [
    "Risk_ID",
    "Account",
    "GL_Reference",
    "Risk_Area",
    "Assertion",
    "Rule_Triggered",
    "Amount",
    "Risk_Score",
    "Risk_Level",
    "Suggested_Procedure",
    "Evidence_Needed",
    "Owner",
    "Status",
    "Comment",
]


def _is_round_number(val: float) -> bool:
    v = abs(float(val))
    return v >= 10_000 and (v % 10_000 == 0 or v % 5_000 == 0)


def run_revenue_and_expense_review(
    adjusted_tb: pd.DataFrame,
    gl_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
    setup: EntitySetup,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Perform Revenue & Expense transaction-level and account-level review (Section 6.1 & 6.2)."""
    if adjusted_tb.empty:
        return pd.DataFrame(columns=REVIEW_COLUMNS), pd.DataFrame(columns=REVIEW_COLUMNS)

    map_lookup = mapping_df.set_index("Account_Code").to_dict(orient="index") if not mapping_df.empty else {}
    p_end = pd.Timestamp(setup.period_end)
    mat = max(1.0, float(setup.materiality_amount))

    rev_rows: list[dict[str, Any]] = []
    exp_rows: list[dict[str, Any]] = []
    rev_seq = 1
    exp_seq = 1

    def add_rev(acct: str, gl_ref: str, area: str, assertion: str, rule: str, amt: float, score: float, proc: str, evid: str) -> None:
        nonlocal rev_seq
        rev_rows.append(
            {
                "Risk_ID": f"REV-{rev_seq:03d}",
                "Account": acct,
                "GL_Reference": gl_ref,
                "Risk_Area": area,
                "Assertion": assertion,
                "Rule_Triggered": rule,
                "Amount": round(float(amt), 2),
                "Risk_Score": round(float(score), 1),
                "Risk_Level": score_risk_level(score, setup.risk_low_max, setup.risk_medium_max, setup.risk_high_max),
                "Suggested_Procedure": f"Suggested Audit Procedure: {proc}",
                "Evidence_Needed": evid,
                "Owner": "Accountant / Auditor",
                "Status": "Open",
                "Comment": "เป็นข้อบ่งชี้จากรูปแบบข้อมูลเพื่อการสอบทานเพิ่มเติม ไม่ใช่ข้อสรุปว่ามีการทุจริต",
            }
        )
        rev_seq += 1

    def add_exp(acct: str, gl_ref: str, area: str, assertion: str, rule: str, amt: float, score: float, proc: str, evid: str) -> None:
        nonlocal exp_seq
        exp_rows.append(
            {
                "Risk_ID": f"EXP-{exp_seq:03d}",
                "Account": acct,
                "GL_Reference": gl_ref,
                "Risk_Area": area,
                "Assertion": assertion,
                "Rule_Triggered": rule,
                "Amount": round(float(amt), 2),
                "Risk_Score": round(float(score), 1),
                "Risk_Level": score_risk_level(score, setup.risk_low_max, setup.risk_medium_max, setup.risk_high_max),
                "Suggested_Procedure": f"Suggested Audit Procedure: {proc}",
                "Evidence_Needed": evid,
                "Owner": "Accountant / Auditor",
                "Status": "Open",
                "Comment": "เป็นข้อบ่งชี้จากรูปแบบข้อมูลเพื่อการสอบทานเพิ่มเติม ไม่ใช่ข้อสรุปว่ามีการทุจริต",
            }
        )
        exp_seq += 1

    # Account-level TB fluctuation checks
    for _, r in adjusted_tb.iterrows():
        code = str(r["Account_Code"])
        acct_label = f"{code} - {r['Account_Name']}"
        grp = str(r.get("Grouping", ""))
        cy = float(r["Adjusted_FS_Amount"])
        py = float(r.get("Prior_Balance", 0.0))

        if grp in ("รายได้จากการขายหรือการให้บริการ", "รายได้อื่น"):
            if abs(py) > 1.0 and abs(cy - py) / abs(py) >= 0.30:
                add_rev(
                    acct_label,
                    "TB Period Comparison",
                    "ความผันผวนของรายได้จากงวดก่อน",
                    "Accuracy, Occurrence",
                    f"รายได้เปลี่ยนแปลง {((cy-py)/abs(py))*100:+.1f}% เทียบงวดก่อน",
                    cy,
                    60.0 if abs(cy) >= mat else 40.0,
                    "วิเคราะห์ความผันผวนรายเดือน/รายผลิตภัณฑ์ (Analytical Review) และสอบทานสัญญาลูกค้ารายสำคัญ",
                    "สรุปรายได้รายเดือน และสัญญาลูกค้าหลัก",
                )
            if bool(map_lookup.get(code, {}).get("Related_Party_Flag")):
                add_rev(
                    acct_label,
                    "COA Related Party Flag",
                    "รายได้กับบุคคล/กิจการที่เกี่ยวข้องกัน",
                    "Presentation and Disclosure",
                    "บัญชีรายได้ระบุเป็นกิจการที่เกี่ยวข้องกัน",
                    cy,
                    65.0,
                    "ตรวจสอบราคาขายเทียบตลาด (Arm's Length) และความครบถ้วนของการเปิดเผยข้อมูลในหมายเหตุ",
                    "สัญญาระหว่างกัน หนังสือยืนยันยอดระหว่างกัน",
                )

        if grp in ("ต้นทุนขายหรือต้นทุนการให้บริการ", "ค่าใช้จ่ายในการขาย", "ค่าใช้จ่ายในการบริหาร", "ค่าใช้จ่ายทางการเงิน", "รายการพิเศษหรือรายการที่ต้องสอบทาน"):
            if abs(py) > 1.0 and abs(cy - py) / abs(py) >= 0.30:
                add_exp(
                    acct_label,
                    "TB Period Comparison",
                    "ความผันผวนของค่าใช้จ่ายจากงวดก่อน",
                    "Accuracy, Completeness",
                    f"ค่าใช้จ่ายเปลี่ยนแปลง {((cy-py)/abs(py))*100:+.1f}% เทียบงวดก่อน",
                    cy,
                    55.0 if abs(cy) >= mat else 35.0,
                    "วิเคราะห์สาเหตุการเปลี่ยนแปลงเทียบงวดก่อนและสุ่มตรวจใบสำคัญจ่ายรายใหญ่",
                    "งบเปรียบเทียบค่าใช้จ่ายรายเดือน และใบสำคัญจ่าย",
                )

    # Transaction-level GL checks
    if gl_df is not None and not gl_df.empty:
        rev_codes = set(adjusted_tb[adjusted_tb["Grouping"].isin(["รายได้จากการขายหรือการให้บริการ", "รายได้อื่น"])]["Account_Code"])
        exp_codes = set(adjusted_tb[adjusted_tb["Grouping"].isin(["ต้นทุนขายหรือต้นทุนการให้บริการ", "ค่าใช้จ่ายในการขาย", "ค่าใช้จ่ายในการบริหาร", "ค่าใช้จ่ายทางการเงิน", "รายการพิเศษหรือรายการที่ต้องสอบทาน"])]["Account_Code"])

        # Revenue GL rules
        rev_gl = gl_df[gl_df["Account_Code"].isin(rev_codes)]
        for _, g in rev_gl.iterrows():
            acct = f"{g['Account_Code']} - {g['Account_Name']}"
            amt = max(float(g["Debit"]), float(g["Credit"]))
            desc = str(g["Description"]).lower()
            ref = str(g["Reference"]).strip()
            dt = g["Date"]
            is_manual = ("manual" in str(g["Entry_Type"]).lower()) or str(g["Doc_No"]).upper().startswith(("JV", "AJ", "JE"))

            if pd.notna(dt) and dt >= p_end - pd.Timedelta(days=7) and dt <= p_end:
                add_rev(acct, g["GL_Ref"], "Revenue Cut-off", "Cut-off", "บันทึกรายได้ช่วง 7 วันสุดท้ายก่อนวันสิ้นงวด", amt, 75.0 if amt >= mat * 0.5 else 50.0, "ตรวจใบส่งของ/ใบตรวจรับงานว่าส่งมอบความเสี่ยงและผลตอบแทนภายในงวดจริง", "ใบกำกับภาษีขาย, ใบส่งของ (DO), ใบตรวจรับงาน")
            if pd.notna(dt) and dt > p_end:
                add_rev(acct, g["GL_Ref"], "Post-close Revenue", "Cut-off", "บันทึกรายได้หรือกลับรายการหลังวันสิ้นงวด", amt, 85.0, "สอบทานเหตุผลในการบันทึกหลังวันสิ้นงวดและผลกระทบต่อการปิดงบ", "ใบสำคัญปรับปรุง และเอกสารประกอบ")
            if is_manual:
                add_rev(acct, g["GL_Ref"], "Manual Journal in Revenue", "Existence, Classification", "บันทึกรายได้ด้วย Manual Journal (ความเสี่ยง Management Override)", amt, 70.0, "สอบทานผู้อนุมัติและเอกสารรองรับรายการ Manual Journal ในบัญชีรายได้", "JV อนุมัติแล้ว, สัญญา/ใบแจ้งหนี้")
            if _is_round_number(amt):
                add_rev(acct, g["GL_Ref"], "Round Amount Revenue", "Accuracy", "ยอดเงินรายได้เป็นตัวเลขกลมผิดปกติ", amt, 45.0, "ตรวจสอบใบแจ้งหนี้และการคำนวณเทียบราคาตามสัญญา", "ใบแจ้งหนี้, สัญญาขาย")
            if not ref:
                add_rev(acct, g["GL_Ref"], "Missing Invoice/Ref", "Existence", "รายการรายได้ไม่มีเลขที่อ้างอิง/ใบแจ้งหนี้", amt, 65.0, "ขอเอกสารใบกำกับภาษี/หลักฐานอ้างอิงรายการรายได้จากฝ่ายบัญชี", "ใบกำกับภาษีขาย / เอกสารอ้างอิง")
            if float(g["Debit"]) > 0 and any(k in desc for k in ["คืน", "ส่วนลด", "ลดหนี้", "กลับรายการ", "return", "credit note", "rebate", "discount", "revers"]):
                add_rev(acct, g["GL_Ref"], "Sales Return / Credit Note", "Accuracy, Cut-off", "รายการลดหนี้/รับคืนสินค้า/ส่วนลดจ่ายในบัญชีรายได้", amt, 55.0, "ตรวจสอบใบลดหนี้และตรวจการรับคืนสินค้าเข้าคลัง", "ใบลดหนี้ (Credit Note), ใบรับคืนสินค้า")
            if any(k in desc for k in ["รับล่วงหน้า", "มัดจำ", "advance", "deposit", "unearned"]):
                add_rev(acct, g["GL_Ref"], "Advance Receipt / Deferred Revenue", "Cut-off, Classification", "คำอธิบายระบุเงินรับล่วงหน้า/มัดจำในบัญชีรายได้", amt, 75.0, "ตรวจสอบว่าได้ส่งมอบสินค้า/บริการครบถ้วนแล้วหรือควรตั้งเป็นรายได้รับล่วงหน้า", "สัญญา, หลักฐานการส่งมอบ")

        # Expense GL rules
        exp_gl = gl_df[gl_df["Account_Code"].isin(exp_codes)]
        dup_exp_mask = exp_gl.duplicated(subset=["Account_Code", "Debit", "Credit", "Description"], keep=False)
        for idx_g, g in exp_gl.iterrows():
            acct = f"{g['Account_Code']} - {g['Account_Name']}"
            amt = max(float(g["Debit"]), float(g["Credit"]))
            desc = str(g["Description"]).lower()
            ref = str(g["Reference"]).strip()
            dt = g["Date"]

            if pd.notna(dt) and dt >= p_end - pd.Timedelta(days=7) and dt <= p_end:
                add_exp(acct, g["GL_Ref"], "Expense Cut-off", "Cut-off", "บันทึกค่าใช้จ่ายช่วง 7 วันสุดท้ายก่อนสิ้นงวด", amt, 55.0 if amt >= mat * 0.5 else 38.0, "ตรวจงวดการให้บริการ/รับมอบสินค้าว่าตรงงวดบัญชี", "ใบแจ้งหนี้, ใบรับของ/บริการ")
            if not ref:
                add_exp(acct, g["GL_Ref"], "Missing Supporting Ref", "Existence, Accuracy", "รายการค่าใช้จ่ายไม่มีเลขที่เอกสารอ้างอิง", amt, 65.0, "ขอใบกำกับภาษี/ใบเสร็จรับเงินและเอกสารอนุมัติจ่าย", "ใบสำคัญจ่าย, ใบกำกับภาษี")
            if _is_round_number(amt):
                add_exp(acct, g["GL_Ref"], "Round Amount Expense", "Accuracy", "ค่าใช้จ่ายยอดเงินกลม (อาจเป็นประมาณการหรือรายการพิเศษ)", amt, 42.0, "ตรวจสัญญา/หลักเกณฑ์การคำนวณและอนุมัติจ่าย", "สัญญา, ใบแจ้งหนี้")
            if amt >= mat * 0.3 and any(k in desc for k in ["เครื่อง", "อุปกรณ์", "คอมพิวเตอร์", "ปรับปรุง", "ก่อสร้าง", "ซอฟต์แวร์", "equipment", "computer", "renovation", "software", "asset"]):
                add_exp(acct, g["GL_Ref"], "Potential Capital Expenditure", "Classification", "ค่าใช้จ่ายมูลค่าสูงที่อาจเข้าเกณฑ์บันทึกเป็นสินทรัพย์ถาวร/ไม่มีตัวตน", amt, 70.0, "สอบทานเกณฑ์การรับรู้สินทรัพย์ (Capitalization Policy) และอายุการใช้งาน", "ใบกำกับภาษี, รายละเอียดงาน/อุปกรณ์")
            if any(k in desc for k in ["กรรมการ", "ผู้บริหาร", "ส่วนตัว", "รับรอง", "director", "personal", "entertainment", "related"]):
                add_exp(acct, g["GL_Ref"], "Director / Related / Entertainment", "Classification, Presentation and Disclosure", "ค่าใช้จ่ายที่เกี่ยวข้องกับกรรมการ/ค่ารับรอง/อาจเป็นรายการส่วนตัวหรือภาษีต้องห้าม", amt, 72.0, "ตรวจวัตถุประสงค์ทางธุรกิจ ระเบียบบริษัท และการบวกกลับทางภาษี (ภ.ง.ด.50)", "ใบเสร็จ, อนุมัติกรรมการ, หลักฐานทางธุรกิจ")
            if dup_exp_mask.loc[idx_g]:
                add_exp(acct, g["GL_Ref"], "Potential Duplicate Expense", "Occurrence, Accuracy", "พบรายการค่าใช้จ่ายที่มีบัญชี จำนวนเงิน และคำอธิบายซ้ำกัน", amt, 62.0, "ตรวจสอบใบแจ้งหนี้ว่าเป็นการจ่ายซ้ำหรือรายการประจำรายเดือน", "ใบแจ้งหนี้, หลักฐานการโอนเงิน")
            if any(k in desc for k in ["ประมาณการ", "สำรอง", "ค่าปรับ", "คดี", "ฟ้อง", "provision", "penalty", "fine", "legal"]):
                add_exp(acct, g["GL_Ref"], "Estimate / Commitment / Tax Non-deductible", "Valuation, Presentation and Disclosure", "รายการลักษณะประมาณการ ค่าปรับ หรืออาจต้องเปิดเผยหนี้สินที่อาจเกิดขึ้น", amt, 68.0, "สอบทานสมมติฐานการประมาณการ การเปิดเผยภาระผูกพัน และรายจ่ายต้องห้ามทางภาษี", "หนังสือทวงถาม/สัญญา/คำนวณประมาณการ")

    rev_df = pd.DataFrame(rev_rows, columns=REVIEW_COLUMNS) if rev_rows else pd.DataFrame(columns=REVIEW_COLUMNS)
    exp_df = pd.DataFrame(exp_rows, columns=REVIEW_COLUMNS) if exp_rows else pd.DataFrame(columns=REVIEW_COLUMNS)
    return rev_df, exp_df


def build_supplementary_audit_sheets(
    adjusted_tb: pd.DataFrame,
    gl_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
    setup: EntitySetup,
) -> dict[str, pd.DataFrame]:
    """Build Confirmation_Request_List, Subsequent_Events, Related_Party_Check, and Tax_Check sheets."""
    if adjusted_tb.empty:
        empty = pd.DataFrame()
        return {
            "Confirmation_Request_List": empty,
            "Subsequent_Events": empty,
            "Related_Party_Check": empty,
            "Tax_Check": empty,
        }

    # 1. Confirmation Request List
    conf_targets = adjusted_tb[
        adjusted_tb["Grouping"].isin(
            [
                "สินทรัพย์หมุนเวียน",
                "หนี้สินหมุนเวียน",
                "หนี้สินไม่หมุนเวียน",
            ]
        )
        & adjusted_tb["Sub_Grouping"].isin(
            [
                "เงินสดและรายการเทียบเท่าเงินสด",
                "ลูกหนี้การค้าและลูกหนี้อื่น",
                "เจ้าหนี้การค้าและเจ้าหนี้อื่น",
                "เงินกู้ยืมระยะสั้นและส่วนที่ถึงกำหนดภายในหนึ่งปี",
                "เงินกู้ยืมระยะยาว",
            ]
        )
        & (adjusted_tb["Adjusted_Net"].abs() > 0.01)
    ]
    conf_rows = []
    for i, (_, r) in enumerate(conf_targets.iterrows(), start=1):
        conf_type = "Bank Confirmation" if "เงินสด" in r["Sub_Grouping"] else (
            "Loan Confirmation" if "เงินกู้" in r["Sub_Grouping"] else (
                "AR Confirmation" if "ลูกหนี้" in r["Sub_Grouping"] else "AP Confirmation"
            )
        )
        conf_rows.append(
            {
                "Confirm_ID": f"CONF-{i:03d}",
                "Confirmation_Type": conf_type,
                "Account_Code": r["Account_Code"],
                "Account_Name": r["Account_Name"],
                "Book_Balance": round(float(r["Adjusted_FS_Amount"]), 2),
                "Material_Flag": abs(float(r["Adjusted_Net"])) >= setup.materiality_amount,
                "Counterparty_Name": "[รอระบุชื่อธนาคาร/คู่ค้า]",
                "Confirmed_Balance": None,
                "Difference": None,
                "Status": "To Be Sent (Suggested)",
            }
        )
    conf_df = pd.DataFrame(conf_rows)

    # 2. Subsequent Events
    sub_rows = []
    if gl_df is not None and not gl_df.empty:
        p_end = pd.Timestamp(setup.period_end)
        post = gl_df[gl_df["Date"].notna() & (gl_df["Date"] > p_end)]
        for _, g in post.iterrows():
            sub_rows.append(
                {
                    "Date": str(g["Date"].date()),
                    "Doc_No": g["Doc_No"],
                    "Account_Code": g["Account_Code"],
                    "Account_Name": g["Account_Name"],
                    "Amount": round(max(float(g["Debit"]), float(g["Credit"])), 2),
                    "Description": g["Description"],
                    "GL_Reference": g["GL_Ref"],
                    "Assessment": "Needs CPA/Management Review (Adjusting vs Non-Adjusting Event)",
                }
            )
    if not sub_rows:
        sub_rows.append(
            {
                "Date": str(setup.period_end),
                "Doc_No": "-",
                "Account_Code": "-",
                "Account_Name": "ไม่พบรายการหลังวันสิ้นงวดในไฟล์ GL ที่นำเข้า",
                "Amount": 0.0,
                "Description": "[ข้อมูลไม่เพียงพอ: ต้องขอ GL เดือนถัดไปและรายงานการประชุมหลังวันสิ้นงวดเพื่อสอบทาน Subsequent Events]",
                "GL_Reference": "N/A",
                "Assessment": "Insufficient Source Data",
            }
        )
    sub_df = pd.DataFrame(sub_rows)

    # 3. Related Party Check
    rp_codes = set()
    if not mapping_df.empty:
        rp_codes = set(mapping_df[mapping_df["Related_Party_Flag"] == True]["Account_Code"])
    rp_tb = adjusted_tb[adjusted_tb["Account_Code"].isin(rp_codes)]
    rp_rows = []
    for _, r in rp_tb.iterrows():
        rp_rows.append(
            {
                "Account_Code": r["Account_Code"],
                "Account_Name": r["Account_Name"],
                "Grouping": r["Grouping"],
                "Adjusted_Amount": round(float(r["Adjusted_FS_Amount"]), 2),
                "Relationship_Nature": "[รอระบุความสัมพันธ์จากฝ่ายบริหาร]",
                "Terms_And_Pricing": "[รอตรวจสอบเงื่อนไข Arm's Length]",
                "Disclosure_Note": "Note 18",
                "Status": "Requires Management Input",
            }
        )
    if not rp_rows:
        rp_rows.append(
            {
                "Account_Code": "-",
                "Account_Name": "ไม่พบบัญชีที่ถูกติดธง Related Party อัตโนมัติ",
                "Grouping": "-",
                "Adjusted_Amount": 0.0,
                "Relationship_Nature": "[ต้องยืนยันจากรายชื่อผู้ถือหุ้น บอจ.5 และกรรมการ]",
                "Terms_And_Pricing": "-",
                "Disclosure_Note": "Note 18",
                "Status": "Requires Management Confirmation",
            }
        )
    rp_df = pd.DataFrame(rp_rows)

    # 4. Tax Check
    tax_tb = adjusted_tb[
        adjusted_tb["Account_Name"].str.contains("ภาษี|vat|wht|หัก ณ ที่จ่าย|ภ.ง.ด|tax", case=False, na=False)
        | (adjusted_tb["Grouping"] == "ภาษีเงินได้")
    ]
    tax_rows = []
    for _, r in tax_tb.iterrows():
        tax_rows.append(
            {
                "Account_Code": r["Account_Code"],
                "Account_Name": r["Account_Name"],
                "Grouping": r["Grouping"],
                "Book_Balance": round(float(r["Adjusted_FS_Amount"]), 2),
                "Tax_Return_Ref": "ภ.พ.30 / ภ.ง.ด.3,53 / ภ.ง.ด.50",
                "Reconciliation_Status": "Pending Tax Return Reconciliation",
                "Comment": "กระทบยอดกับแบบแสดงรายการภาษีที่ยื่นต่อกรมสรรพากร",
            }
        )
    tax_df = pd.DataFrame(tax_rows)

    return {
        "Confirmation_Request_List": conf_df,
        "Subsequent_Events": sub_df,
        "Related_Party_Check": rp_df,
        "Tax_Check": tax_df,
    }
