from __future__ import annotations

from pathlib import Path
import sys

import fitz
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config_loader import get_grouping_master_df


def build_mapping_template() -> None:
    out_path = ROOT / "config" / "account_mapping_template.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gm_df = get_grouping_master_df()
    sample_map = pd.DataFrame(
        [
            {
                "Account_Code": "110101",
                "Account_Name": "เงินสดในมือ",
                "Normal_Balance": "Debit",
                "Account_Type": "Asset",
                "FS_Sign": 1,
                "Current_Non_Current": "Current",
                "Grouping": "สินทรัพย์หมุนเวียน",
                "Sub_Grouping": "เงินสดและรายการเทียบเท่าเงินสด",
                "Financial_Statement": "FS_Balance_Sheet",
                "Statement_Section": "สินทรัพย์หมุนเวียน",
                "FS_Line_Item": "เงินสดและรายการเทียบเท่าเงินสด",
                "Detail_Sheet": "D_Cash_Bank",
                "Note_No": "4",
                "Cash_Flow_Class": "Cash",
                "Tax_Classification": "Standard",
                "Related_Party_Flag": False,
                "Significant_Account_Flag": True,
                "DBD_Line_Item": "เงินสดและรายการเทียบเท่าเงินสด",
                "Mapping_Method": "User Confirmed",
                "Confidence_Score": 100,
                "Reviewer_Status": "Approved",
                "Reviewer_Comment": "ตัวอย่างโครงสร้าง Mapping",
                "Source_Standard_Ref": "TFRS for NPAEs บทที่ 6",
            }
        ]
    )
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        sample_map.to_excel(writer, sheet_name="COA_Mapping_Template", index=False)
        gm_df.to_excel(writer, sheet_name="Grouping_Master", index=False)


def build_sample_data() -> None:
    sdir = ROOT / "sample_data"
    sdir.mkdir(parents=True, exist_ok=True)

    # Balanced Trial Balance (Prior Year balanced too: Assets = Liab + Equity + Prior Net Income already in Prior RE)
    tb_rows = [
        # Assets
        ("110101", "เงินสดในมือ", "HQ", 50000.0, 85000.0, 0.0, 85000.0, 50000.0),
        ("110201", "เงินฝากธนาคารกสิกรไทย - ออมทรัพย์", "HQ", 1150000.0, 2150000.0, 0.0, 2150000.0, 1150000.0),
        ("112101", "ลูกหนี้การค้า - กิจการที่ไม่เกี่ยวข้องกัน", "Sales", 820000.0, 1450000.0, 0.0, 1450000.0, 820000.0),
        ("112901", "ค่าเผื่อหนี้สงสัยจะสูญ", "Sales", -20000.0, 0.0, 45000.0, -45000.0, -20000.0),
        ("115101", "สินค้าคงเหลือ - สินค้าสำเร็จรูป", "Warehouse", 650000.0, 920000.0, 0.0, 920000.0, 650000.0),
        ("117101", "ภาษีซื้อรอขอคืน", "HQ", 35000.0, 48000.0, 0.0, 48000.0, 35000.0),
        ("123101", "เครื่องตกแต่งและอุปกรณ์สำนักงาน", "HQ", 1800000.0, 2200000.0, 0.0, 2200000.0, 1800000.0),
        ("123901", "ค่าเสื่อมราคาสะสม - อุปกรณ์สำนักงาน", "HQ", -360000.0, 0.0, 620000.0, -620000.0, -360000.0),
        # Liabilities
        ("211101", "เจ้าหนี้การค้า - ในประเทศ", "HQ", -420000.0, 0.0, 680000.0, -680000.0, -420000.0),
        ("214101", "ค่าใช้จ่ายค้างจ่าย", "HQ", -85000.0, 0.0, 130000.0, -130000.0, -85000.0),
        ("215101", "ภาษีเงินได้นิติบุคคลค้างจ่าย", "HQ", -90000.0, 0.0, 165000.0, -165000.0, -90000.0),
        ("220101", "เงินกู้ยืมระยะยาวจากสถาบันการเงิน", "HQ", -1000000.0, 0.0, 800000.0, -800000.0, -1000000.0),
        # Equity
        ("310101", "ทุนจดทะเบียนและชำระแล้ว", "HQ", -2000000.0, 0.0, 2000000.0, -2000000.0, -2000000.0),
        ("320101", "กำไรสะสมที่ยังไม่ได้จัดสรร", "HQ", -530000.0, 0.0, 530000.0, -530000.0, -530000.0),
        # Revenue & Expenses (Current Year)
        ("410101", "รายได้จากการขายสินค้า", "Sales", 0.0, 0.0, 6800000.0, -6800000.0, 0.0),
        ("410201", "รายได้จากการให้บริการ", "Service", 0.0, 0.0, 1200000.0, -1200000.0, 0.0),
        ("420101", "ดอกเบี้ยรับและรายได้อื่น", "HQ", 0.0, 0.0, 45000.0, -45000.0, 0.0),
        ("510101", "ต้นทุนขายสินค้า", "Warehouse", 0.0, 4120000.0, 0.0, 4120000.0, 0.0),
        ("520101", "ค่าใช้จ่ายในการขายและการตลาด", "Sales", 0.0, 580000.0, 0.0, 580000.0, 0.0),
        ("530101", "เงินเดือนและค่าจ้างพนักงานบริหาร", "Admin", 0.0, 960000.0, 0.0, 960000.0, 0.0),
        ("530201", "ค่าเช่าสำนักงานและสาธารณูปโภค", "Admin", 0.0, 360000.0, 0.0, 360000.0, 0.0),
        ("531001", "ค่าเสื่อมราคา", "Admin", 0.0, 260000.0, 0.0, 260000.0, 0.0),
        ("532001", "ค่ารับรองและค่าที่ปรึกษา", "Admin", 0.0, 165000.0, 0.0, 165000.0, 0.0),
        ("540101", "ดอกเบี้ยจ่ายเงินกู้ยืม", "HQ", 0.0, 42000.0, 0.0, 42000.0, 0.0),
        ("550101", "ค่าใช้จ่ายภาษีเงินได้นิติบุคคล", "HQ", 0.0, 275000.0, 0.0, 275000.0, 0.0),
    ]
    # Check balance:
    # Assets Dr: 85k+2150k+1450k+920k+48k+2200k = 6,853k; Cr: 45k+620k = 665k -> Net Assets = 6,188k
    # Liab+Eq Cr: 680k+130k+165k+800k+2000k+530k = 4,305k
    # Rev Cr: 6800k+1200k+45k = 8,045k
    # Exp Dr: 4120k+580k+960k+360k+260k+165k+42k+275k = 6,762k
    # Net Income = 8,045k - 6,762k = 1,283k
    # Assets (6,188k) vs Liab+Eq+NI (4,305k + 1,283k = 5,588k) -> diff 600k! Let's adjust Share Capital to 2,600,000 so Assets = Liab + Eq!
    tb_df = pd.DataFrame(
        tb_rows,
        columns=["Account Code", "Account Name", "Department", "Opening Balance", "Debit", "Credit", "Balance", "Prior Balance"],
    )
    # Fix Share Capital and Prior RE so both Current Year TB and Prior Year Opening are 100% balanced!
    # Prior Net Assets = 50k+1150k+820k-20k+650k+35k+1800k-360k = 4,125,000
    # Prior Liab = 420k+85k+90k+1000k = 1,595,000 -> Prior Equity must be 4,125,000 - 1,595,000 = 2,530,000!
    # Wait: Current Year Net Income = 1,283,000; Current Net Assets = 6,188,000; Current Liab = 1,775,000
    # -> Current Equity needed = 6,188,000 - 1,775,000 = 4,413,000 -> Beginning Equity needed = 4,413,000 - 1,283,000 = 3,130,000!
    # So Share Capital = 2,600,000 and Retained Earnings = 530,000 -> 3,130,000! And adjust Prior Cash by +600,000 (1,750,000) so Prior Assets = 4,725,000 = 1,595,000 + 3,130,000!
    tb_df.loc[tb_df["Account Code"] == "310101", ["Opening Balance", "Credit", "Balance", "Prior Balance"]] = [-2600000.0, 2600000.0, -2600000.0, -2600000.0]
    tb_df.loc[tb_df["Account Code"] == "110201", ["Opening Balance", "Prior Balance"]] = [1750000.0, 1750000.0]
    assert abs(tb_df["Debit"].sum() - tb_df["Credit"].sum()) < 0.01, f"TB unbalanced: {tb_df['Debit'].sum()} vs {tb_df['Credit'].sum()}"
    assert abs(tb_df["Prior Balance"].sum()) < 0.01, f"Prior TB unbalanced: {tb_df['Prior Balance'].sum()}"

    with pd.ExcelWriter(sdir / "sample_tb.xlsx", engine="openpyxl") as writer:
        tb_df.to_excel(writer, sheet_name="Trial_Balance", index=False)

    # Sample GL with balanced journals covering realistic audit patterns (Cut-off, Manual JV, Round amount, Missing Ref, Entertainment)
    gl_rows = [
        ("2025-02-10", "RV-2025-001", "110201", "เงินฝากธนาคารกสิกรไทย - ออมทรัพย์", 2400000.0, 0.0, "รับชำระค่าขายสินค้าล็อต Q1", "INV-2025-001", "CC-01", "Sales", "THB", "System", "UserA"),
        ("2025-02-10", "RV-2025-001", "410101", "รายได้จากการขายสินค้า", 0.0, 2400000.0, "รับชำระค่าขายสินค้าล็อต Q1", "INV-2025-001", "CC-01", "Sales", "THB", "System", "UserA"),

        ("2025-06-15", "RV-2025-045", "112101", "ลูกหนี้การค้า - กิจการที่ไม่เกี่ยวข้องกัน", 3200000.0, 0.0, "ขายสินค้าเงินเชื่อให้ลูกค้าหลัก", "INV-2025-045", "CC-01", "Sales", "THB", "System", "UserA"),
        ("2025-06-15", "RV-2025-045", "410101", "รายได้จากการขายสินค้า", 0.0, 3200000.0, "ขายสินค้าเงินเชื่อให้ลูกค้าหลัก", "INV-2025-045", "CC-01", "Sales", "THB", "System", "UserA"),

        ("2025-08-20", "PV-2025-088", "510101", "ต้นทุนขายสินค้า", 4120000.0, 0.0, "บันทึกต้นทุนสินค้าที่จำหน่ายระหว่างงวด", "COST-2025-08", "CC-02", "Warehouse", "THB", "System", "UserB"),
        ("2025-08-20", "PV-2025-088", "115101", "สินค้าคงเหลือ - สินค้าสำเร็จรูป", 0.0, 4120000.0, "บันทึกต้นทุนสินค้าที่จำหน่ายระหว่างงวด", "COST-2025-08", "CC-02", "Warehouse", "THB", "System", "UserB"),

        ("2025-11-30", "PV-2025-112", "532001", "ค่ารับรองและค่าที่ปรึกษา", 100000.0, 0.0, "ค่าที่ปรึกษาและค่ารับรองกรรมการผู้บริหาร", "", "CC-03", "Admin", "THB", "Manual", "Manager1"),
        ("2025-11-30", "PV-2025-112", "110201", "เงินฝากธนาคารกสิกรไทย - ออมทรัพย์", 0.0, 100000.0, "ค่าที่ปรึกษาและค่ารับรองกรรมการผู้บริหาร", "", "CC-03", "Admin", "THB", "Manual", "Manager1"),

        ("2025-12-20", "PV-2025-130", "530101", "เงินเดือนและค่าจ้างพนักงานบริหาร", 960000.0, 0.0, "เงินเดือนและโบนัสพนักงานบริหารประจำปี", "PAY-2025-12", "CC-03", "Admin", "THB", "System", "HR1"),
        ("2025-12-20", "PV-2025-130", "110201", "เงินฝากธนาคารกสิกรไทย - ออมทรัพย์", 0.0, 960000.0, "เงินเดือนและโบนัสพนักงานบริหารประจำปี", "PAY-2025-12", "CC-03", "Admin", "THB", "System", "HR1"),

        ("2025-12-29", "JV-2025-901", "112101", "ลูกหนี้การค้า - กิจการที่ไม่เกี่ยวข้องกัน", 1200000.0, 0.0, "รับรู้รายได้จากการขายช่วงปลายงวด (Cut-off review)", "INV-2025-998", "CC-01", "Sales", "THB", "Manual", "Manager1"),
        ("2025-12-29", "JV-2025-901", "410101", "รายได้จากการขายสินค้า", 0.0, 1200000.0, "รับรู้รายได้จากการขายช่วงปลายงวด (Cut-off review)", "INV-2025-998", "CC-01", "Sales", "THB", "Manual", "Manager1"),

        ("2025-12-30", "JV-2025-902", "112101", "ลูกหนี้การค้า - กิจการที่ไม่เกี่ยวข้องกัน", 1200000.0, 0.0, "รายได้ค่าบริการรายปี (รวมค่าบริการรับล่วงหน้า)", "", "CC-01", "Service", "THB", "Manual", "Manager1"),
        ("2025-12-30", "JV-2025-902", "410201", "รายได้จากการให้บริการ", 0.0, 1200000.0, "รายได้ค่าบริการรายปี (รวมค่าบริการรับล่วงหน้า)", "", "CC-01", "Service", "THB", "Manual", "Manager1"),

        ("2025-12-31", "JV-2025-905", "531001", "ค่าเสื่อมราคา", 260000.0, 0.0, "บันทึกค่าเสื่อมราคาประจำปี 2025", "FA-DEP-2025", "CC-03", "Admin", "THB", "Adjusting", "Accountant1"),
        ("2025-12-31", "JV-2025-905", "123901", "ค่าเสื่อมราคาสะสม - อุปกรณ์สำนักงาน", 0.0, 260000.0, "บันทึกค่าเสื่อมราคาประจำปี 2025", "FA-DEP-2025", "CC-03", "Admin", "THB", "Adjusting", "Accountant1"),
    ]
    gl_df = pd.DataFrame(
        gl_rows,
        columns=[
            "Date", "Document No", "Account Code", "Account Name", "Debit", "Credit",
            "Description", "Reference", "Cost Center", "Department", "Currency", "Entry Type", "Posted By",
        ],
    )
    with pd.ExcelWriter(sdir / "sample_gl.xlsx", engine="openpyxl") as writer:
        gl_df.to_excel(writer, sheet_name="General_Ledger", index=False)

    # Sample Prior Year FS (Excel + Text PDF)
    py_bs = pd.DataFrame(
        [
            {"รายการ": "บริษัท ตัวอย่าง การค้า จำกัด — งบแสดงฐานะการเงิน ณ 31 ธันวาคม 2024", "หมายเหตุ": "", "2024": None},
            {"รายการ": "เงินสดและรายการเทียบเท่าเงินสด", "หมายเหตุ": "4", "2024": 1800000.0},
            {"รายการ": "ลูกหนี้การค้าและลูกหนี้อื่น", "หมายเหตุ": "5", "2024": 800000.0},
            {"รายการ": "สินค้าคงเหลือ", "หมายเหตุ": "6", "2024": 650000.0},
            {"รายการ": "สินทรัพย์หมุนเวียนอื่น", "หมายเหตุ": "5", "2024": 35000.0},
            {"รายการ": "ที่ดิน อาคารและอุปกรณ์", "หมายเหตุ": "8", "2024": 1440000.0},
            {"รายการ": "เจ้าหนี้การค้าและเจ้าหนี้อื่น", "หมายเหตุ": "11", "2024": 420000.0},
            {"รายการ": "ค่าใช้จ่ายค้างจ่าย", "หมายเหตุ": "11", "2024": 85000.0},
            {"รายการ": "ภาษีเงินได้ค้างจ่ายและภาษีอื่น", "หมายเหตุ": "13", "2024": 90000.0},
            {"รายการ": "เงินกู้ยืมระยะยาว", "หมายเหตุ": "12", "2024": 1000000.0},
            {"รายการ": "ทุนที่ออกและชำระแล้ว", "หมายเหตุ": "16", "2024": 2600000.0},
            {"รายการ": "กำไรสะสม", "หมายเหตุ": "16", "2024": 530000.0},
        ]
    )
    with pd.ExcelWriter(sdir / "sample_prior_year_fs.xlsx", engine="openpyxl") as writer:
        py_bs.to_excel(writer, sheet_name="Balance_Sheet_2024", index=False)

    # Also build text PDF prior year FS using PyMuPDF
    doc = fitz.open()
    page = doc.new_page()
    pdf_lines = [
        "Sample Trading Co., Ltd. (2024 Financial Statements)",
        "Statement of Financial Position as at 31 December 2024",
        "Cash and cash equivalents          1,800,000.00",
        "Trade and other receivables          800,000.00",
        "Inventories                          650,000.00",
        "Other current assets                  35,000.00",
        "Property, plant and equipment      1,440,000.00",
        "Trade and other payables             420,000.00",
        "Accrued expenses                      85,000.00",
        "Income tax payable                    90,000.00",
        "Long-term borrowings               1,000,000.00",
        "Issued and paid-up share capital   2,600,000.00",
        "Retained earnings                    530,000.00",
    ]
    y = 60
    for ln in pdf_lines:
        page.insert_text((50, y), ln, fontsize=11)
        y += 22
    doc.save(str(sdir / "sample_prior_year_fs.pdf"))
    doc.close()


if __name__ == "__main__":
    build_mapping_template()
    build_sample_data()
    print("Generated config/account_mapping_template.xlsx and sample_data/* successfully.")
