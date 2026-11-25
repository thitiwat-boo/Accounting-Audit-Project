from __future__ import annotations

from typing import Any
import pandas as pd

from src.models import EntitySetup


def _build_prior_lookup(prior_review_df: pd.DataFrame | None, use_prior_mode: str, adjusted_tb: pd.DataFrame) -> dict[str, float]:
    """Return prior year amounts keyed by FS_Line_Item only when confirmed or present in comparative mode."""
    lookup: dict[str, float] = {}
    if use_prior_mode == "Do Not Use":
        return lookup

    if prior_review_df is not None and not prior_review_df.empty and use_prior_mode == "Comparative Source":
        confirmed = prior_review_df[prior_review_df["UserConfirmed"] == True]
        for _, r in confirmed.iterrows():
            key = str(r.get("Mapped_FS_Line_Item") or "").strip()
            if key:
                lookup[key] = lookup.get(key, 0.0) + float(r.get("ExtractedAmount", 0.0) or 0.0)
        if lookup:
            return lookup

    # Fallback to TB Prior_Balance only if non-zero
    if not adjusted_tb.empty and adjusted_tb["Prior_Balance"].abs().sum() > 0.01:
        grp = adjusted_tb.groupby("FS_Line_Item")["Prior_Balance"].sum()
        return grp.to_dict()
    return lookup


def build_financial_statements(
    adjusted_tb: pd.DataFrame,
    setup: EntitySetup,
    prior_review_df: pd.DataFrame | None = None,
    use_prior_mode: str = "Comparative Source",
) -> dict[str, Any]:
    """Build Balance Sheet, Income Statement, Changes in Equity, and reconciliation checks with full formula/source metadata."""
    if adjusted_tb.empty:
        return {
            "balance_sheet": pd.DataFrame(),
            "income_statement": pd.DataFrame(),
            "changes_in_equity": pd.DataFrame(),
            "unmapped": pd.DataFrame(),
            "reconciliations": {},
            "warnings": ["ยังไม่มีข้อมูล Adjusted TB กรุณานำเข้าข้อมูลและทำ Mapping ก่อน"],
        }

    div = setup.unit_divisor
    prior_map = _build_prior_lookup(prior_review_df, use_prior_mode, adjusted_tb)

    # Separate unmapped/suspense items
    unmapped = adjusted_tb[
        adjusted_tb["Mapping_Status"].isin(["Unmapped", "Rejected"])
        | adjusted_tb["Grouping"].str.contains("จัดประเภทไม่ได้|บัญชีพัก", na=False)
    ].copy()
    mapped = adjusted_tb[~adjusted_tb.index.isin(unmapped.index)].copy()

    # Helper to aggregate by Grouping & FS_Line_Item
    def line_info(grouping: str, fs_line: str, detail_sheet: str, note_no: str) -> dict[str, Any]:
        sub = mapped[(mapped["Grouping"] == grouping) & (mapped["FS_Line_Item"] == fs_line)]
        if sub.empty:
            sub = mapped[mapped["FS_Line_Item"] == fs_line]
        cy = float(sub["Adjusted_FS_Amount"].sum()) / div
        py = float(prior_map.get(fs_line, 0.0)) / div
        accts = ", ".join(sub["Account_Code"].astype(str).tolist())
        return {
            "cy": cy,
            "py": py,
            "accts": accts,
            "detail_sheet": detail_sheet,
            "note_no": note_no,
            "formula_desc": f"=SUMIFS(Adjusted_TB!$S:$S, Adjusted_TB!$F:$F, \"{fs_line}\") / {int(div)}",
            "excel_formula_preview": f"={detail_sheet}!H_TOTAL",
            "source_ref": f"{detail_sheet} ({len(sub)} บัญชี: {accts or 'ไม่มี'})",
        }

    # --- 1. INCOME STATEMENT ---
    rev_sales = line_info("รายได้จากการขายหรือการให้บริการ", "รายได้จากการขายหรือการให้บริการ", "D_Revenue", "17")
    other_inc = line_info("รายได้อื่น", "รายได้อื่น", "D_Other_Income_Expense", "17")
    cogs = line_info("ต้นทุนขายหรือต้นทุนการให้บริการ", "ต้นทุนขายหรือต้นทุนการให้บริการ", "D_Cost_of_Sales_or_Service", "17")
    selling = line_info("ค่าใช้จ่ายในการขาย", "ค่าใช้จ่ายในการขาย", "D_Selling_Expenses", "17")
    admin = line_info("ค่าใช้จ่ายในการบริหาร", "ค่าใช้จ่ายในการบริหาร", "D_Administrative_Expenses", "17")
    other_exp = line_info("รายการพิเศษหรือรายการที่ต้องสอบทาน", "ค่าใช้จ่ายอื่น / รายการรอตรวจสอบ", "D_Other_Income_Expense", "17")
    fin_cost = line_info("ค่าใช้จ่ายทางการเงิน", "ต้นทุนทางการเงิน", "D_Finance_Cost", "12")
    tax_exp = line_info("ภาษีเงินได้", "ค่าใช้จ่ายภาษีเงินได้", "D_Income_Tax", "13")

    gross_profit_cy = rev_sales["cy"] - cogs["cy"]
    gross_profit_py = rev_sales["py"] - cogs["py"]
    ebit_cy = gross_profit_cy + other_inc["cy"] - selling["cy"] - admin["cy"] - other_exp["cy"]
    ebit_py = gross_profit_py + other_inc["py"] - selling["py"] - admin["py"] - other_exp["py"]
    ebt_cy = ebit_cy - fin_cost["cy"]
    ebt_py = ebit_py - fin_cost["py"]
    net_income_cy = ebt_cy - tax_exp["cy"]
    net_income_py = ebt_py - tax_exp["py"]

    is_rows: list[dict[str, Any]] = [
        {"Section": "รายได้", "Line_Item": "รายได้จากการขายหรือการให้บริการ", "Note": "17", "Current_Year": rev_sales["cy"], "Prior_Year": rev_sales["py"], "Row_Type": "Line", "Formula_Preview": rev_sales["excel_formula_preview"], "Source_Ref": rev_sales["source_ref"]},
        {"Section": "ต้นทุน", "Line_Item": "หัก ต้นทุนขายหรือต้นทุนการให้บริการ", "Note": "17", "Current_Year": -cogs["cy"], "Prior_Year": -cogs["py"], "Row_Type": "Line", "Formula_Preview": f"=-{cogs['excel_formula_preview'][1:]}", "Source_Ref": cogs["source_ref"]},
        {"Section": "กำไรขั้นต้น", "Line_Item": "กำไร (ขาดทุน) ขั้นต้น", "Note": "", "Current_Year": gross_profit_cy, "Prior_Year": gross_profit_py, "Row_Type": "Subtotal", "Formula_Preview": "=F6+F7", "Source_Ref": "Calculated Subtotal"},
        {"Section": "รายได้อื่น", "Line_Item": "บวก รายได้อื่น", "Note": "17", "Current_Year": other_inc["cy"], "Prior_Year": other_inc["py"], "Row_Type": "Line", "Formula_Preview": other_inc["excel_formula_preview"], "Source_Ref": other_inc["source_ref"]},
        {"Section": "ค่าใช้จ่าย", "Line_Item": "หัก ค่าใช้จ่ายในการขาย", "Note": "17", "Current_Year": -selling["cy"], "Prior_Year": -selling["py"], "Row_Type": "Line", "Formula_Preview": f"=-{selling['excel_formula_preview'][1:]}", "Source_Ref": selling["source_ref"]},
        {"Section": "ค่าใช้จ่าย", "Line_Item": "หัก ค่าใช้จ่ายในการบริหาร", "Note": "17", "Current_Year": -admin["cy"], "Prior_Year": -admin["py"], "Row_Type": "Line", "Formula_Preview": f"=-{admin['excel_formula_preview'][1:]}", "Source_Ref": admin["source_ref"]},
    ]
    if abs(other_exp["cy"]) > 0.001 or abs(other_exp["py"]) > 0.001:
        is_rows.append(
            {"Section": "ค่าใช้จ่าย", "Line_Item": "หัก ค่าใช้จ่ายอื่น / รายการรอตรวจสอบ", "Note": "17", "Current_Year": -other_exp["cy"], "Prior_Year": -other_exp["py"], "Row_Type": "Line", "Formula_Preview": f"=-{other_exp['excel_formula_preview'][1:]}", "Source_Ref": other_exp["source_ref"]}
        )
    is_rows.extend(
        [
            {"Section": "กำไรจากการดำเนินงาน", "Line_Item": "กำไร (ขาดทุน) ก่อนต้นทุนทางการเงินและภาษีเงินได้ (EBIT)", "Note": "", "Current_Year": ebit_cy, "Prior_Year": ebit_py, "Row_Type": "Subtotal", "Formula_Preview": "=SUM(F8:F11)", "Source_Ref": "Calculated Subtotal"},
            {"Section": "ต้นทุนทางการเงิน", "Line_Item": "หัก ต้นทุนทางการเงิน", "Note": "12", "Current_Year": -fin_cost["cy"], "Prior_Year": -fin_cost["py"], "Row_Type": "Line", "Formula_Preview": f"=-{fin_cost['excel_formula_preview'][1:]}", "Source_Ref": fin_cost["source_ref"]},
            {"Section": "กำไรก่อนภาษี", "Line_Item": "กำไร (ขาดทุน) ก่อนค่าใช้จ่ายภาษีเงินได้", "Note": "", "Current_Year": ebt_cy, "Prior_Year": ebt_py, "Row_Type": "Subtotal", "Formula_Preview": "=F12+F13", "Source_Ref": "Calculated Subtotal"},
            {"Section": "ภาษีเงินได้", "Line_Item": "หัก ค่าใช้จ่ายภาษีเงินได้", "Note": "13", "Current_Year": -tax_exp["cy"], "Prior_Year": -tax_exp["py"], "Row_Type": "Line", "Formula_Preview": f"=-{tax_exp['excel_formula_preview'][1:]}", "Source_Ref": tax_exp["source_ref"]},
            {"Section": "กำไรสุทธิ", "Line_Item": "กำไร (ขาดทุน) สุทธิสำหรับงวด", "Note": "", "Current_Year": net_income_cy, "Prior_Year": net_income_py, "Row_Type": "Total", "Formula_Preview": "=F14+F15", "Source_Ref": "Calculated Net Income -> Equity"},
        ]
    )
    if setup.framework == "TFRS for PAEs / TFRS เต็มรูปแบบ":
        is_rows.append(
            {"Section": "กำไรขาดทุนเบ็ดเสร็จอื่น", "Line_Item": "กำไรขาดทุนเบ็ดเสร็จอื่นสำหรับงวด (OCI - ถ้ามี)", "Note": "", "Current_Year": 0.0, "Prior_Year": 0.0, "Row_Type": "Line", "Formula_Preview": "=0", "Source_Ref": "[รอข้อมูลจากฝ่ายบริหาร: ตรวจสอบรายการ OCI]"}
        )
        is_rows.append(
            {"Section": "กำไรขาดทุนเบ็ดเสร็จรวม", "Line_Item": "กำไร (ขาดทุน) เบ็ดเสร็จรวมสำหรับงวด", "Note": "", "Current_Year": net_income_cy, "Prior_Year": net_income_py, "Row_Type": "Total", "Formula_Preview": "=F16+F17", "Source_Ref": "Total Comprehensive Income"}
        )
    is_df = pd.DataFrame(is_rows)

    # --- 2. BALANCE SHEET ---
    bs_spec = [
        ("สินทรัพย์หมุนเวียน", "เงินสดและรายการเทียบเท่าเงินสด", "D_Cash_Bank", "4"),
        ("สินทรัพย์หมุนเวียน", "ลูกหนี้การค้าและลูกหนี้อื่น", "D_AR_Trade_Other", "5"),
        ("สินทรัพย์หมุนเวียน", "สินค้าคงเหลือ", "D_Inventory", "6"),
        ("สินทรัพย์หมุนเวียน", "สินทรัพย์หมุนเวียนอื่น", "D_Other_Current_Assets", "5"),
    ]
    nca_spec = [
        ("สินทรัพย์ไม่หมุนเวียน", "เงินลงทุนในบริษัทย่อย บริษัทร่วม และเงินลงทุนระยะยาว", "D_Investments", "7"),
        ("สินทรัพย์ไม่หมุนเวียน", "ที่ดิน อาคารและอุปกรณ์", "D_PPE", "8"),
        ("สินทรัพย์ไม่หมุนเวียน", "สินทรัพย์ไม่มีตัวตน", "D_Intangible_Assets", "9"),
    ]
    cl_spec = [
        ("หนี้สินหมุนเวียน", "เงินเบิกเกินบัญชีและเงินกู้ยืมระยะสั้น", "D_Borrowings", "12"),
        ("หนี้สินหมุนเวียน", "เจ้าหนี้การค้าและเจ้าหนี้อื่น", "D_AP_Trade_Other", "11"),
        ("หนี้สินหมุนเวียน", "ค่าใช้จ่ายค้างจ่าย", "D_Accrued_Expenses", "11"),
        ("หนี้สินหมุนเวียน", "ภาษีเงินได้ค้างจ่ายและภาษีอื่น", "D_Tax_Payable", "13"),
    ]
    ncl_spec = [
        ("หนี้สินไม่หมุนเวียน", "เงินกู้ยืมระยะยาว", "D_Borrowings", "12"),
        ("หนี้สินไม่หมุนเวียน", "หนี้สินตามสัญญาเช่า", "D_Lease_Liabilities", "10"),
        ("หนี้สินไม่หมุนเวียน", "ประมาณการหนี้สินไม่หมุนเวียนสำหรับผลประโยชน์พนักงาน", "D_Employee_Benefits", "14"),
        ("หนี้สินไม่หมุนเวียน", "ประมาณการหนี้สินอื่น", "D_Provisions", "15"),
    ]

    bs_rows: list[dict[str, Any]] = []
    ca_cy, ca_py = 0.0, 0.0
    for grp, line, ds, note in bs_spec:
        info = line_info(grp, line, ds, note)
        ca_cy += info["cy"]
        ca_py += info["py"]
        bs_rows.append({"Section": "สินทรัพย์หมุนเวียน", "Line_Item": line, "Note": note, "Current_Year": info["cy"], "Prior_Year": info["py"], "Row_Type": "Line", "Formula_Preview": info["excel_formula_preview"], "Source_Ref": info["source_ref"]})
    bs_rows.append({"Section": "สินทรัพย์หมุนเวียน", "Line_Item": "รวมสินทรัพย์หมุนเวียน", "Note": "", "Current_Year": ca_cy, "Prior_Year": ca_py, "Row_Type": "Subtotal", "Formula_Preview": "=SUM(Current_Assets)", "Source_Ref": "Subtotal"})

    nca_cy, nca_py = 0.0, 0.0
    for grp, line, ds, note in nca_spec:
        info = line_info(grp, line, ds, note)
        nca_cy += info["cy"]
        nca_py += info["py"]
        bs_rows.append({"Section": "สินทรัพย์ไม่หมุนเวียน", "Line_Item": line, "Note": note, "Current_Year": info["cy"], "Prior_Year": info["py"], "Row_Type": "Line", "Formula_Preview": info["excel_formula_preview"], "Source_Ref": info["source_ref"]})
    bs_rows.append({"Section": "สินทรัพย์ไม่หมุนเวียน", "Line_Item": "รวมสินทรัพย์ไม่หมุนเวียน", "Note": "", "Current_Year": nca_cy, "Prior_Year": nca_py, "Row_Type": "Subtotal", "Formula_Preview": "=SUM(NonCurrent_Assets)", "Source_Ref": "Subtotal"})

    tot_assets_cy = ca_cy + nca_cy
    tot_assets_py = ca_py + nca_py
    bs_rows.append({"Section": "รวมสินทรัพย์", "Line_Item": "รวมสินทรัพย์", "Note": "", "Current_Year": tot_assets_cy, "Prior_Year": tot_assets_py, "Row_Type": "Total", "Formula_Preview": "=Subtotal_CA+Subtotal_NCA", "Source_Ref": "Total Assets"})

    cl_cy, cl_py = 0.0, 0.0
    for grp, line, ds, note in cl_spec:
        info = line_info(grp, line, ds, note)
        cl_cy += info["cy"]
        cl_py += info["py"]
        bs_rows.append({"Section": "หนี้สินหมุนเวียน", "Line_Item": line, "Note": note, "Current_Year": info["cy"], "Prior_Year": info["py"], "Row_Type": "Line", "Formula_Preview": info["excel_formula_preview"], "Source_Ref": info["source_ref"]})
    bs_rows.append({"Section": "หนี้สินหมุนเวียน", "Line_Item": "รวมหนี้สินหมุนเวียน", "Note": "", "Current_Year": cl_cy, "Prior_Year": cl_py, "Row_Type": "Subtotal", "Formula_Preview": "=SUM(Current_Liab)", "Source_Ref": "Subtotal"})

    ncl_cy, ncl_py = 0.0, 0.0
    for grp, line, ds, note in ncl_spec:
        info = line_info(grp, line, ds, note)
        ncl_cy += info["cy"]
        ncl_py += info["py"]
        bs_rows.append({"Section": "หนี้สินไม่หมุนเวียน", "Line_Item": line, "Note": note, "Current_Year": info["cy"], "Prior_Year": info["py"], "Row_Type": "Line", "Formula_Preview": info["excel_formula_preview"], "Source_Ref": info["source_ref"]})
    bs_rows.append({"Section": "หนี้สินไม่หมุนเวียน", "Line_Item": "รวมหนี้สินไม่หมุนเวียน", "Note": "", "Current_Year": ncl_cy, "Prior_Year": ncl_py, "Row_Type": "Subtotal", "Formula_Preview": "=SUM(NonCurrent_Liab)", "Source_Ref": "Subtotal"})

    tot_liab_cy = cl_cy + ncl_cy
    tot_liab_py = cl_py + ncl_py
    bs_rows.append({"Section": "รวมหนี้สิน", "Line_Item": "รวมหนี้สิน", "Note": "", "Current_Year": tot_liab_cy, "Prior_Year": tot_liab_py, "Row_Type": "Subtotal", "Formula_Preview": "=Subtotal_CL+Subtotal_NCL", "Source_Ref": "Total Liabilities"})

    # Equity: Share Capital + Retained Earnings (Opening/TB RE + Current Year Net Income)
    cap_info = line_info("ส่วนของเจ้าของ", "ทุนที่ออกและชำระแล้ว", "D_Share_Capital", "16")
    re_info = line_info("ส่วนของเจ้าของ", "กำไรสะสม", "D_Retained_Earnings", "16")
    # Note: In TB before closing entries, P&L accounts are not closed into Retained Earnings yet,
    # so Ending Retained Earnings = TB Retained Earnings + Current Year Net Income!
    re_ending_cy = re_info["cy"] + net_income_cy
    re_ending_py = re_info["py"] + (0.0 if prior_map else 0.0)
    tot_eq_cy = cap_info["cy"] + re_ending_cy
    tot_eq_py = cap_info["py"] + re_ending_py

    bs_rows.append({"Section": "ส่วนของเจ้าของ", "Line_Item": "ทุนที่ออกและชำระแล้ว", "Note": "16", "Current_Year": cap_info["cy"], "Prior_Year": cap_info["py"], "Row_Type": "Line", "Formula_Preview": cap_info["excel_formula_preview"], "Source_Ref": cap_info["source_ref"]})
    bs_rows.append({"Section": "ส่วนของเจ้าของ", "Line_Item": "กำไรสะสม (รวมกำไรสุทธิประจำงวด)", "Note": "16", "Current_Year": re_ending_cy, "Prior_Year": re_ending_py, "Row_Type": "Line", "Formula_Preview": f"={re_info['excel_formula_preview'][1:]}+FS_Income_Statement!NetIncome", "Source_Ref": f"{re_info['source_ref']} + Net Income ({net_income_cy:,.2f})"})
    bs_rows.append({"Section": "ส่วนของเจ้าของ", "Line_Item": "รวมส่วนของเจ้าของ", "Note": "", "Current_Year": tot_eq_cy, "Prior_Year": tot_eq_py, "Row_Type": "Subtotal", "Formula_Preview": "=SUM(Equity_Lines)", "Source_Ref": "Total Equity"})
    bs_rows.append({"Section": "รวมหนี้สินและส่วนของเจ้าของ", "Line_Item": "รวมหนี้สินและส่วนของเจ้าของ", "Note": "", "Current_Year": tot_liab_cy + tot_eq_cy, "Prior_Year": tot_liab_py + tot_eq_py, "Row_Type": "Total", "Formula_Preview": "=Total_Liab+Total_Equity", "Source_Ref": "Total Liabilities & Equity"})

    bs_df = pd.DataFrame(bs_rows)

    # --- 3. STATEMENT OF CHANGES IN EQUITY ---
    # Split RE movement if dividends exist in TB/GL
    sce_df = pd.DataFrame(
        [
            {"Item": "ยอดคงเหลือต้นงวด", "Share_Capital": cap_info["cy"], "Retained_Earnings": re_info["cy"], "Total_Equity": cap_info["cy"] + re_info["cy"], "Formula_Preview": "=D_Share_Capital+D_Retained_Earnings_Opening"},
            {"Item": "กำไร (ขาดทุน) สุทธิสำหรับงวด", "Share_Capital": 0.0, "Retained_Earnings": net_income_cy, "Total_Equity": net_income_cy, "Formula_Preview": "=FS_Income_Statement!NetIncome"},
            {"Item": "ยอดคงเหลือปลายงวด", "Share_Capital": cap_info["cy"], "Retained_Earnings": re_ending_cy, "Total_Equity": tot_eq_cy, "Formula_Preview": "=SUM(Opening:Movement)"},
        ]
    )

    bs_diff_cy = round(tot_assets_cy - (tot_liab_cy + tot_eq_cy), 2)
    unmapped_net = float(unmapped["Adjusted_Net"].sum()) / div if not unmapped.empty else 0.0

    warnings: list[str] = []
    if not unmapped.empty:
        warnings.append(f"มีบัญชีที่ยังไม่ได้จัดประเภท (Unmapped/Suspense) จำนวน {len(unmapped)} บัญชี ยอดสุทธิ {unmapped_net:,.2f} — ห้ามออกงบฉบับ Final")
    if abs(bs_diff_cy) > 0.01:
        warnings.append(f"งบแสดงฐานะการเงินยังไม่สมดุล: สินทรัพย์ - (หนี้สิน + ส่วนของเจ้าของ) = {bs_diff_cy:,.2f} (อาจเกิดจากบัญชียังไม่ mapping หรือ TB ไม่สมดุล)")
    if not prior_map:
        warnings.append("ยังไม่มีข้อมูลงวดเปรียบเทียบที่ยืนยันแล้ว — แสดงยอดปีก่อนเป็น 0")

    return {
        "balance_sheet": bs_df,
        "income_statement": is_df,
        "changes_in_equity": sce_df,
        "unmapped": unmapped,
        "reconciliations": {
            "total_assets": tot_assets_cy,
            "total_liabilities": tot_liab_cy,
            "total_equity": tot_eq_cy,
            "bs_balance_diff": bs_diff_cy,
            "net_income": net_income_cy,
            "gross_profit": gross_profit_cy,
            "ebit": ebit_cy,
            "revenue": rev_sales["cy"],
            "cash_ending": line_info("สินทรัพย์หมุนเวียน", "เงินสดและรายการเทียบเท่าเงินสด", "D_Cash_Bank", "4")["cy"],
            "unmapped_count": len(unmapped),
            "unmapped_net": unmapped_net,
        },
        "warnings": warnings,
    }
