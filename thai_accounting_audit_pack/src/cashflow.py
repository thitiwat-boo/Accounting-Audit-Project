from __future__ import annotations

from typing import Any
import pandas as pd

from src.models import EntitySetup


def build_cash_flow_statement(
    adjusted_tb: pd.DataFrame,
    gl_df: pd.DataFrame,
    fs_result: dict[str, Any],
    setup: EntitySetup,
    prior_review_df: pd.DataFrame | None = None,
    use_prior_mode: str = "Comparative Source",
) -> dict[str, Any]:
    """Build Indirect or Direct Cash Flow Statement with strict sufficiency guard (Section 8 & H)."""
    if adjusted_tb.empty or not fs_result.get("reconciliations"):
        return {
            "status": "Insufficient Data",
            "message": "ต้องใช้ข้อมูลธนาคาร/รายละเอียดรายการเงินสดเพิ่มเติม (ยังไม่มี Adjusted TB)",
            "cashflow_df": pd.DataFrame(),
            "ending_cash_cf": 0.0,
            "ending_cash_bs": 0.0,
            "reconciled": False,
        }

    div = setup.unit_divisor
    rec = fs_result["reconciliations"]
    bs_cash_ending = float(rec.get("cash_ending", 0.0))
    net_income = float(rec.get("net_income", 0.0))

    # Check whether we have beginning cash (from Opening_Balance / Prior_Balance / Prior Year confirmed)
    cash_rows = adjusted_tb[adjusted_tb["FS_Line_Item"] == "เงินสดและรายการเทียบเท่าเงินสด"]
    has_cash_accounts = not cash_rows.empty
    if not has_cash_accounts:
        return {
            "status": "Insufficient Data",
            "message": "ต้องใช้ข้อมูลธนาคาร/รายละเอียดรายการเงินสดเพิ่มเติม (ไม่พบบัญชีที่ map เป็นเงินสดและรายการเทียบเท่าเงินสด)",
            "cashflow_df": pd.DataFrame(),
            "ending_cash_cf": 0.0,
            "ending_cash_bs": bs_cash_ending,
            "reconciled": False,
        }

    # Beginning cash: check TB Prior_Balance or confirmed prior year
    cash_beginning = float(cash_rows["Prior_Balance"].sum()) / div
    has_prior_cash = abs(cash_rows["Prior_Balance"].sum()) > 0.01

    if not has_prior_cash and prior_review_df is not None and not prior_review_df.empty and use_prior_mode == "Comparative Source":
        conf_cash = prior_review_df[
            (prior_review_df["UserConfirmed"] == True)
            & (prior_review_df["Mapped_FS_Line_Item"] == "เงินสดและรายการเทียบเท่าเงินสด")
        ]
        if not conf_cash.empty:
            cash_beginning = float(conf_cash["ExtractedAmount"].sum()) / div
            has_prior_cash = True

    # Guard: if Direct method requested without GL cash transactions, OR Indirect without prior-year balance / opening cash movement
    if setup.cashflow_method == "ทางตรง (Direct)":
        if gl_df.empty:
            return {
                "status": "Insufficient Data",
                "message": "ต้องใช้ข้อมูลธนาคาร/รายละเอียดรายการเงินสดเพิ่มเติม (วิธีทางตรงต้องใช้ข้อมูล GL บัญชีเงินสดและธนาคารรายรายการ)",
                "cashflow_df": pd.DataFrame(),
                "ending_cash_cf": 0.0,
                "ending_cash_bs": bs_cash_ending,
                "reconciled": False,
            }
        cash_codes = set(cash_rows["Account_Code"].astype(str))
        cash_gl = gl_df[gl_df["Account_Code"].astype(str).isin(cash_codes)].copy()
        if cash_gl.empty:
            return {
                "status": "Insufficient Data",
                "message": "ต้องใช้ข้อมูลธนาคาร/รายละเอียดรายการเงินสดเพิ่มเติม (ไม่พบรายการเคลื่อนไหวเงินสดใน GL)",
                "cashflow_df": pd.DataFrame(),
                "ending_cash_cf": 0.0,
                "ending_cash_bs": bs_cash_ending,
                "reconciled": False,
            }
        # Classify cash receipts & payments from GL descriptions / counterpart
        inflows = float(cash_gl["Debit"].sum()) / div
        outflows = float(cash_gl["Credit"].sum()) / div
        net_cf = inflows - outflows
        if not has_prior_cash:
            cash_beginning = bs_cash_ending - net_cf
        ending_cf = cash_beginning + net_cf
        cf_rows = [
            {"Category": "กิจกรรมดำเนินงาน (วิธีทางตรง)", "Line_Item": "เงินสดรับจากการดำเนินงานและแหล่งอื่นตาม GL บัญชีเงินสด", "Amount": inflows, "Formula_Preview": "=SUMIFS(GL_Normalized!Debit, Cash_Accounts)", "Status": "From GL - Needs Classification Review"},
            {"Category": "กิจกรรมดำเนินงาน (วิธีทางตรง)", "Line_Item": "เงินสดจ่ายเพื่อการดำเนินงานและรายการอื่นตาม GL บัญชีเงินสด", "Amount": -outflows, "Formula_Preview": "=-SUMIFS(GL_Normalized!Credit, Cash_Accounts)", "Status": "From GL - Needs Classification Review"},
            {"Category": "สรุปกระแสเงินสด", "Line_Item": "เงินสดและรายการเทียบเท่าเงินสดเพิ่มขึ้น (ลดลง) สุทธิ", "Amount": net_cf, "Formula_Preview": "=SUM(Cash_Flow_Lines)", "Status": "Calculated"},
            {"Category": "สรุปกระแสเงินสด", "Line_Item": "เงินสดและรายการเทียบเท่าเงินสดต้นงวด", "Amount": cash_beginning, "Formula_Preview": "=Prior_Cash_Balance", "Status": "Confirmed" if has_prior_cash else "Derived from Ending - Net Change (Needs Verification)"},
            {"Category": "สรุปกระแสเงินสด", "Line_Item": "เงินสดและรายการเทียบเท่าเงินสดปลายงวด", "Amount": ending_cf, "Formula_Preview": "=Net_Change+Beginning_Cash", "Status": "Reconciled to Balance Sheet" if abs(ending_cf - bs_cash_ending) < 0.01 else "Variance Detected"},
        ]
        return {
            "status": "Draft Generated" if has_prior_cash else "Partial - Needs Bank/Opening Verification",
            "message": "จัดทำเพิ่มเติมตามความประสงค์/นโยบายของกิจการ" if setup.framework == "TFRS for NPAEs" else "",
            "cashflow_df": pd.DataFrame(cf_rows),
            "ending_cash_cf": ending_cf,
            "ending_cash_bs": bs_cash_ending,
            "reconciled": abs(ending_cf - bs_cash_ending) < 0.01,
        }

    # Indirect method: requires comparative balances to compute working capital / investing / financing changes
    if not has_prior_cash and adjusted_tb["Prior_Balance"].abs().sum() < 0.01:
        return {
            "status": "Insufficient Data",
            "message": "ต้องใช้ข้อมูลธนาคาร/รายละเอียดรายการเงินสดเพิ่มเติม (งบทดลองไม่มีข้อมูลงวดเปรียบเทียบเพื่อคำนวณการเปลี่ยนแปลงเงินทุนหมุนเวียนในวิธีทางอ้อม)",
            "cashflow_df": pd.DataFrame(),
            "ending_cash_cf": 0.0,
            "ending_cash_bs": bs_cash_ending,
            "reconciled": False,
        }

    # Build Indirect CF from Adjusted_FS_Amount vs Prior_Balance
    # Non-cash depreciation/amortization
    depr_rows = adjusted_tb[adjusted_tb["Account_Name"].str.contains("ค่าเสื่อมราคา|ค่าตัดจำหน่าย|depreciation|amortization", case=False, na=False) & (adjusted_tb["Account_Type"] == "Expense")]
    depr_amt = float(depr_rows["Adjusted_FS_Amount"].sum()) / div

    def delta_line(fs_line: str) -> float:
        sub = adjusted_tb[adjusted_tb["FS_Line_Item"] == fs_line]
        return float((sub["Adjusted_FS_Amount"] - sub["Prior_Balance"]).sum()) / div

    # Working capital changes: Asset increase -> cash outflow (-), Liability increase -> cash inflow (+)
    d_ar = -delta_line("ลูกหนี้การค้าและลูกหนี้อื่น")
    d_inv = -delta_line("สินค้าคงเหลือ")
    d_oca = -delta_line("สินทรัพย์หมุนเวียนอื่น")
    d_ap = delta_line("เจ้าหนี้การค้าและเจ้าหนี้อื่น")
    d_acc = delta_line("ค่าใช้จ่ายค้างจ่าย")
    d_tax_pay = delta_line("ภาษีเงินได้ค้างจ่ายและภาษีอื่น")

    cfo = net_income + depr_amt + d_ar + d_inv + d_oca + d_ap + d_acc + d_tax_pay

    # Investing: PPE gross movement approximated by -(delta net PPE + depr_amt), Intangibles, Investments
    d_ppe_net = delta_line("ที่ดิน อาคารและอุปกรณ์")
    capex_cf = -(d_ppe_net + depr_amt)
    d_intang = -delta_line("สินทรัพย์ไม่มีตัวตน")
    d_inv_lt = -delta_line("เงินลงทุนในบริษัทย่อย บริษัทร่วม และเงินลงทุนระยะยาว")
    cfi = capex_cf + d_intang + d_inv_lt

    # Financing: Borrowings, Lease, Provisions/Benefits, Share Capital, Unexplained RE diff
    d_st_loan = delta_line("เงินเบิกเกินบัญชีและเงินกู้ยืมระยะสั้น")
    d_lt_loan = delta_line("เงินกู้ยืมระยะยาว")
    d_lease = delta_line("หนี้สินตามสัญญาเช่า")
    d_emp = delta_line("ประมาณการหนี้สินไม่หมุนเวียนสำหรับผลประโยชน์พนักงาน")
    d_prov = delta_line("ประมาณการหนี้สินอื่น")
    d_cap = delta_line("ทุนที่ออกและชำระแล้ว")
    # Dividend/Other RE change = delta(TB RE)
    d_re_other = delta_line("กำไรสะสม")

    cff = d_st_loan + d_lt_loan + d_lease + d_emp + d_prov + d_cap + d_re_other

    net_change = cfo + cfi + cff
    ending_cf = cash_beginning + net_change

    cf_rows = [
        {"Category": "กระแสเงินสดจากกิจกรรมดำเนินงาน", "Line_Item": "กำไร (ขาดทุน) สุทธิสำหรับงวด", "Amount": net_income, "Formula_Preview": "=FS_Income_Statement!NetIncome", "Status": "Linked"},
        {"Category": "กระแสเงินสดจากกิจกรรมดำเนินงาน", "Line_Item": "บวก ค่าเสื่อมราคาและค่าตัดจำหน่าย (รายการที่ไม่ใช่เงินสด)", "Amount": depr_amt, "Formula_Preview": "=SUMIFS(Adjusted_TB!Adjusted_FS_Amount, Depr_Accounts)", "Status": "Needs Asset Register Verification"},
        {"Category": "กระแสเงินสดจากกิจกรรมดำเนินงาน", "Line_Item": "ลูกหนี้การค้าและลูกหนี้อื่น (เพิ่มขึ้น) ลดลง", "Amount": d_ar, "Formula_Preview": "=-(D_AR_Trade_Other!CY - D_AR_Trade_Other!PY)", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมดำเนินงาน", "Line_Item": "สินค้าคงเหลือ (เพิ่มขึ้น) ลดลง", "Amount": d_inv, "Formula_Preview": "=-(D_Inventory!CY - D_Inventory!PY)", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมดำเนินงาน", "Line_Item": "สินทรัพย์หมุนเวียนอื่น (เพิ่มขึ้น) ลดลง", "Amount": d_oca, "Formula_Preview": "=-(D_Other_Current_Assets!CY - D_Other_Current_Assets!PY)", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมดำเนินงาน", "Line_Item": "เจ้าหนี้การค้าและเจ้าหนี้อื่น เพิ่มขึ้น (ลดลง)", "Amount": d_ap, "Formula_Preview": "=D_AP_Trade_Other!CY - D_AP_Trade_Other!PY", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมดำเนินงาน", "Line_Item": "ค่าใช้จ่ายค้างจ่าย เพิ่มขึ้น (ลดลง)", "Amount": d_acc, "Formula_Preview": "=D_Accrued_Expenses!CY - D_Accrued_Expenses!PY", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมดำเนินงาน", "Line_Item": "ภาษีเงินได้ค้างจ่ายและภาษีอื่น เพิ่มขึ้น (ลดลง)", "Amount": d_tax_pay, "Formula_Preview": "=D_Tax_Payable!CY - D_Tax_Payable!PY", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมดำเนินงาน", "Line_Item": "เงินสดสุทธิได้มาจาก (ใช้ไปใน) กิจกรรมดำเนินงาน", "Amount": cfo, "Formula_Preview": "=SUM(CFO_Lines)", "Status": "Subtotal"},
        {"Category": "กระแสเงินสดจากกิจกรรมลงทุน", "Line_Item": "เงินสดจ่ายซื้อที่ดิน อาคารและอุปกรณ์ (สุทธิ)", "Amount": capex_cf, "Formula_Preview": "=-(D_PPE!CY - D_PPE!PY + Depr)", "Status": "Needs Fixed Asset Verification"},
        {"Category": "กระแสเงินสดจากกิจกรรมลงทุน", "Line_Item": "สินทรัพย์ไม่มีตัวตนและเงินลงทุนระยะยาว (เพิ่มขึ้น) ลดลง", "Amount": d_intang + d_inv_lt, "Formula_Preview": "=-(Delta_Intangibles + Delta_Investments)", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมลงทุน", "Line_Item": "เงินสดสุทธิได้มาจาก (ใช้ไปใน) กิจกรรมลงทุน", "Amount": cfi, "Formula_Preview": "=SUM(CFI_Lines)", "Status": "Subtotal"},
        {"Category": "กระแสเงินสดจากกิจกรรมจัดหาเงิน", "Line_Item": "เงินเบิกเกินบัญชีและเงินกู้ยืมระยะสั้น เพิ่มขึ้น (ลดลง)", "Amount": d_st_loan, "Formula_Preview": "=Delta_ST_Borrowings", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมจัดหาเงิน", "Line_Item": "เงินกู้ยืมระยะยาวและหนี้สินตามสัญญาเช่า เพิ่มขึ้น (ลดลง)", "Amount": d_lt_loan + d_lease, "Formula_Preview": "=Delta_LT_Borrowings + Delta_Lease", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมจัดหาเงิน", "Line_Item": "ประมาณการหนี้สิน ทุนเรือนหุ้น และกำไรสะสม (เงินปันผล)", "Amount": d_emp + d_prov + d_cap + d_re_other, "Formula_Preview": "=Delta_Provisions + Delta_Capital + Delta_RE", "Status": "Calculated"},
        {"Category": "กระแสเงินสดจากกิจกรรมจัดหาเงิน", "Line_Item": "เงินสดสุทธิได้มาจาก (ใช้ไปใน) กิจกรรมจัดหาเงิน", "Amount": cff, "Formula_Preview": "=SUM(CFF_Lines)", "Status": "Subtotal"},
        {"Category": "สรุปกระแสเงินสด", "Line_Item": "เงินสดและรายการเทียบเท่าเงินสดเพิ่มขึ้น (ลดลง) สุทธิ", "Amount": net_change, "Formula_Preview": "=CFO+CFI+CFF", "Status": "Calculated"},
        {"Category": "สรุปกระแสเงินสด", "Line_Item": "เงินสดและรายการเทียบเท่าเงินสดต้นงวด", "Amount": cash_beginning, "Formula_Preview": "=D_Cash_Bank!PY_Total", "Status": "Linked"},
        {"Category": "สรุปกระแสเงินสด", "Line_Item": "เงินสดและรายการเทียบเท่าเงินสดปลายงวด", "Amount": ending_cf, "Formula_Preview": "=Net_Change+Beginning_Cash", "Status": "Reconciled" if abs(ending_cf - bs_cash_ending) < 0.01 else "Variance Detected"},
    ]

    msg = "จัดทำเพิ่มเติมตามความประสงค์/นโยบายของกิจการ" if setup.framework == "TFRS for NPAEs" else ""
    return {
        "status": "Draft Generated",
        "message": msg,
        "cashflow_df": pd.DataFrame(cf_rows),
        "ending_cash_cf": ending_cf,
        "ending_cash_bs": bs_cash_ending,
        "reconciled": abs(ending_cf - bs_cash_ending) < 0.01,
    }
