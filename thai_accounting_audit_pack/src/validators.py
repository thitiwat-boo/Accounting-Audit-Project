from __future__ import annotations

from datetime import date
from typing import Any
import pandas as pd


def run_data_quality_checks(
    tb_df: pd.DataFrame,
    gl_df: pd.DataFrame,
    period_start: date,
    period_end: date,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Run comprehensive 14-point TB/GL Data Quality checks (Section 3.2)."""
    checks: list[dict[str, Any]] = []
    details: dict[str, pd.DataFrame] = {}

    def add_check(
        check_id: str,
        category: str,
        name: str,
        status: str,
        issue_count: int,
        impact_amount: float,
        summary: str,
        recommendation: str,
        detail_df: pd.DataFrame | None = None,
    ) -> None:
        checks.append(
            {
                "Check_ID": check_id,
                "Category": category,
                "Check_Name": name,
                "Status": status,
                "Issue_Count": int(issue_count),
                "Impact_Amount": round(float(impact_amount), 2),
                "Summary": summary,
                "Recommendation": recommendation,
            }
        )
        if detail_df is not None and not detail_df.empty:
            details[check_id] = detail_df.copy()

    if tb_df.empty:
        add_check(
            "DQ-00",
            "Input",
            "ความพร้อมของข้อมูล TB",
            "Error",
            1,
            0.0,
            "ยังไม่มีข้อมูล Trial Balance ในระบบ",
            "กรุณานำเข้าไฟล์ TB ในหน้า 'นำเข้าข้อมูล'",
        )
        return pd.DataFrame(checks), details

    # 1. TB Debit = Credit
    tot_dr = float(tb_df["Debit"].sum())
    tot_cr = float(tb_df["Credit"].sum())
    tb_diff = round(tot_dr - tot_cr, 2)
    add_check(
        "DQ-01",
        "Trial Balance",
        "งบทดลองสมดุล (Debit = Credit)",
        "Pass" if abs(tb_diff) < 0.01 else "Error",
        0 if abs(tb_diff) < 0.01 else 1,
        abs(tb_diff),
        f"Dr รวม = {tot_dr:,.2f}, Cr รวม = {tot_cr:,.2f}, ผลต่าง = {tb_diff:,.2f}",
        "ตรวจสอบแถวที่หายไปหรือตัวเลขคอลัมน์ Dr/Cr ในไฟล์ TB ต้นทาง" if abs(tb_diff) >= 0.01 else "งบทดลองสมดุลสมบูรณ์",
    )

    # 2. TB Balance = Debit - Credit
    bal_diff = (tb_df["Net_Balance"] - tb_df["Provided_Balance"]).abs()
    bad_bal = tb_df[bal_diff > 0.01]
    add_check(
        "DQ-02",
        "Trial Balance",
        "ยอดคงเหลือ (Balance = Debit - Credit)",
        "Pass" if bad_bal.empty else "Error",
        len(bad_bal),
        float(bal_diff[bal_diff > 0.01].sum()) if not bad_bal.empty else 0.0,
        f"พบ {len(bad_bal)} บัญชีที่ยอด Balance ไม่ตรงกับ Debit - Credit" if not bad_bal.empty else "ทุกบัญชีคำนวณ Balance ถูกต้อง",
        "ตรวจสอบสูตรยอดคงเหลือในไฟล์ TB ต้นทาง (ระวังเครื่องหมายบวก/ลบในคอลัมน์ Balance)",
        bad_bal,
    )

    # 3. Duplicate account codes or multiple names for same code / multiple codes for same name
    dup_codes = tb_df[tb_df.duplicated(subset=["Account_Code"], keep=False)]
    name_per_code = tb_df.groupby("Account_Code")["Account_Name"].nunique()
    multi_name_codes = name_per_code[name_per_code > 1].index.tolist()
    code_per_name = tb_df.groupby("Account_Name")["Account_Code"].nunique()
    multi_code_names = code_per_name[code_per_name > 1].index.tolist()
    dup_acct_df = tb_df[
        tb_df["Account_Code"].isin(multi_name_codes)
        | tb_df["Account_Name"].isin(multi_code_names)
        | tb_df.index.isin(dup_codes.index)
    ]
    add_check(
        "DQ-03",
        "Chart of Accounts",
        "รหัสบัญชีหรือชื่อบัญชีซ้ำหลายแบบ",
        "Pass" if dup_acct_df.empty else "Warning",
        len(dup_acct_df),
        0.0,
        f"พบ {len(dup_acct_df)} แถวที่รหัสหรือชื่อบัญชีซ้ำ/ไม่สอดคล้องกัน" if not dup_acct_df.empty else "รหัสและชื่อบัญชีใน TB ไม่ซ้ำซ้อน",
        "รวมบัญชีที่มีรหัสซ้ำหรือปรับมาตรฐานชื่อบัญชีให้ตรงกันก่อนทำ Mapping",
        dup_acct_df,
    )

    # 4. Negative or reversed TB numbers
    neg_tb = tb_df[(tb_df["Debit"] < -0.001) | (tb_df["Credit"] < -0.001)]
    add_check(
        "DQ-04",
        "Trial Balance",
        "ยอดเดบิต/เครดิตติดลบผิดปกติใน TB",
        "Pass" if neg_tb.empty else "Warning",
        len(neg_tb),
        float(neg_tb[["Debit", "Credit"]].abs().sum().sum()) if not neg_tb.empty else 0.0,
        f"พบ {len(neg_tb)} แถวใน TB ที่มียอด Dr หรือ Cr ติดลบ" if not neg_tb.empty else "ไม่พบยอด Dr/Cr ติดลบใน TB",
        "ตรวจสอบว่ารายการติดลบเกิดจากการกลับรายการหรือผิดคอลัมน์",
        neg_tb,
    )

    if gl_df.empty:
        add_check(
            "DQ-05",
            "General Ledger",
            "ความพร้อมของข้อมูล GL",
            "Warning",
            1,
            0.0,
            "ยังไม่ได้นำเข้า General Ledger (GL) — ระบบจะตรวจความเสี่ยงระดับรายการไม่ได้",
            "นำเข้าไฟล์ GL เพื่อปลดล็อกการกระทบยอด TB-GL, Cut-off และ Audit Workpaper ระดับรายการ",
        )
        return pd.DataFrame(checks), details

    # 5. Missing or Out-of-period dates in GL
    p_start = pd.Timestamp(period_start)
    p_end = pd.Timestamp(period_end)
    missing_date = gl_df[gl_df["Date"].isna()]
    out_of_period = gl_df[gl_df["Date"].notna() & ((gl_df["Date"] < p_start) | (gl_df["Date"] > p_end))]
    bad_dates = pd.concat([missing_date, out_of_period]).drop_duplicates()
    add_check(
        "DQ-05",
        "General Ledger",
        "วันที่ใน GL ว่างหรืออยู่นอกงวดบัญชี",
        "Pass" if bad_dates.empty else "Error",
        len(bad_dates),
        float(bad_dates["Debit"].sum() + bad_dates["Credit"].sum()) if not bad_dates.empty else 0.0,
        f"วันที่ว่าง {len(missing_date)} แถว, นอกงวด ({period_start} ถึง {period_end}) {len(out_of_period)} แถว",
        "ตรวจสอบรายการผิดงวด (Cut-off / Post-close) หรือแก้ไขรูปแบบวันที่ในไฟล์ต้นทาง",
        bad_dates,
    )

    # 6. Unbalanced GL documents
    doc_sums = gl_df.groupby("Doc_No", dropna=False)[["Debit", "Credit"]].sum()
    doc_sums["Diff"] = (doc_sums["Debit"] - doc_sums["Credit"]).abs()
    unbal_docs = doc_sums[doc_sums["Diff"] > 0.01]
    unbal_gl = gl_df[gl_df["Doc_No"].isin(unbal_docs.index)]
    add_check(
        "DQ-06",
        "General Ledger",
        "รายการ GL ที่เดบิตและเครดิตไม่สมดุลรายเอกสาร",
        "Pass" if unbal_docs.empty else "Error",
        len(unbal_docs),
        float(unbal_docs["Diff"].sum()) if not unbal_docs.empty else 0.0,
        f"พบ {len(unbal_docs)} เลขที่เอกสารที่ผลรวม Dr ไม่เท่ากับ Cr" if not unbal_docs.empty else "ทุกเลขที่เอกสารใน GL สมดุล Dr = Cr",
        "ตรวจสอบใบสำคัญที่บันทึกไม่ครบขาหรือถูกตัดแถวออกระหว่าง Export จากระบบบัญชี",
        unbal_gl,
    )

    # 7. Exact duplicate GL lines
    dup_gl = gl_df[gl_df.duplicated(subset=["Date", "Doc_No", "Account_Code", "Debit", "Credit", "Description"], keep=False)]
    add_check(
        "DQ-07",
        "General Ledger",
        "รายการ GL ซ้ำซ้อนกันทั้งหมด",
        "Pass" if dup_gl.empty else "Warning",
        len(dup_gl),
        float(dup_gl["Debit"].sum()) if not dup_gl.empty else 0.0,
        f"พบ {len(dup_gl)} แถวที่มีข้อมูลซ้ำเหมือนกันทุกฟิลด์หลัก" if not dup_gl.empty else "ไม่พบรายการซ้ำซ้อนแบบตรงทุกฟิลด์ใน GL",
        "สอบทานว่าเป็นการบันทึกรายการเบิ้ลหรือเป็นรายการปกติที่มีมูลค่าเท่ากัน",
        dup_gl,
    )

    # 8. Abnormal duplicate Doc_No across different dates
    doc_dates = gl_df.dropna(subset=["Date"]).groupby("Doc_No")["Date"].nunique()
    multi_date_docs = doc_dates[doc_dates > 1].index.tolist()
    dup_doc_df = gl_df[gl_df["Doc_No"].isin(multi_date_docs)]
    add_check(
        "DQ-08",
        "General Ledger",
        "เลขที่เอกสารซ้ำข้ามวันที่",
        "Pass" if dup_doc_df.empty else "Warning",
        len(multi_date_docs),
        float(dup_doc_df["Debit"].sum()) if not dup_doc_df.empty else 0.0,
        f"พบ {len(multi_date_docs)} เลขที่เอกสารที่ปรากฏหลายวันที่ต่างกัน" if multi_date_docs else "ไม่พบเลขที่เอกสารซ้ำข้ามวันที่",
        "ตรวจสอบการออกเลขที่เอกสารซ้ำหรือการแก้ไขวันที่ภายหลัง",
        dup_doc_df,
    )

    # 9. Accounts in GL missing from TB
    tb_codes = set(tb_df["Account_Code"].astype(str).str.strip())
    gl_codes = set(gl_df["Account_Code"].astype(str).str.strip())
    in_gl_not_tb = sorted(gl_codes - tb_codes)
    gl_missing_df = gl_df[gl_df["Account_Code"].isin(in_gl_not_tb)]
    add_check(
        "DQ-09",
        "Reconciliation",
        "บัญชีที่มีใน GL แต่ไม่พบใน TB",
        "Pass" if not in_gl_not_tb else "Error",
        len(in_gl_not_tb),
        float(gl_missing_df["Net_Amount"].abs().sum()) if not gl_missing_df.empty else 0.0,
        f"พบบัญชีใน GL ที่ไม่อยู่ใน TB จำนวน {len(in_gl_not_tb)} บัญชี: {', '.join(in_gl_not_tb[:5])}" if in_gl_not_tb else "ทุกบัญชีใน GL ปรากฏใน TB ครบถ้วน",
        "ตรวจสอบขอบเขตการ Export TB หรือบัญชีใหม่ที่ยังไม่ถูกรวมในงบทดลอง",
        gl_missing_df,
    )

    # 10. Accounts in TB with zero GL activity
    in_tb_not_gl = sorted(tb_codes - gl_codes)
    tb_no_gl_df = tb_df[tb_df["Account_Code"].isin(in_tb_not_gl)]
    non_zero_no_gl = tb_no_gl_df[tb_no_gl_df["Net_Balance"].abs() > 0.01]
    add_check(
        "DQ-10",
        "Reconciliation",
        "บัญชีใน TB ที่ไม่มีรายการเคลื่อนไหวใน GL",
        "Pass" if tb_no_gl_df.empty else "Warning",
        len(tb_no_gl_df),
        float(non_zero_no_gl["Net_Balance"].abs().sum()) if not non_zero_no_gl.empty else 0.0,
        f"พบ {len(tb_no_gl_df)} บัญชีใน TB ที่ไม่มี GL ในงวด (มียอดคงเหลือ {len(non_zero_no_gl)} บัญชี)",
        "ยืนยันว่าบัญชีที่ไม่มีเคลื่อนไหวเป็นยอดยกมาที่ไม่มีรายการระหว่างปีจริง",
        tb_no_gl_df,
    )

    # 11. Negative or reversed GL amounts
    neg_gl = gl_df[(gl_df["Debit"] < -0.001) | (gl_df["Credit"] < -0.001)]
    add_check(
        "DQ-11",
        "General Ledger",
        "จำนวนเงินติดลบหรือกลับด้านใน GL",
        "Pass" if neg_gl.empty else "Warning",
        len(neg_gl),
        float(neg_gl[["Debit", "Credit"]].abs().sum().sum()) if not neg_gl.empty else 0.0,
        f"พบ {len(neg_gl)} รายการใน GL ที่มีตัวเลขติดลบ" if not neg_gl.empty else "ไม่พบจำนวนเงินติดลบใน GL",
        "สอบทานว่ารายการติดลบเป็นการกลับรายการ (Reversal) หรือข้อผิดพลาดในการบันทึก",
        neg_gl,
    )

    # 12. Manual journals & Post-close entries
    manual_mask = (
        gl_df["Entry_Type"].str.lower().str.contains("manual|adjust|post-close|close|jv", na=False)
        | gl_df["Doc_No"].str.upper().str.startswith(("JV", "AJ", "ADJ", "JE"))
    )
    post_close_mask = gl_df["Date"].notna() & (gl_df["Date"] > p_end)
    manual_df = gl_df[manual_mask | post_close_mask]
    add_check(
        "DQ-12",
        "Audit Trail",
        "รายการ Manual Journal และรายการ Post-Close",
        "Warning" if not manual_df.empty else "Pass",
        len(manual_df),
        float(manual_df["Debit"].sum()) if not manual_df.empty else 0.0,
        f"พบรายการ Manual/Adjusting/Post-Close จำนวน {len(manual_df)} แถว (ต้องสอบทาน Management Override)",
        "เตรียมเอกสารอนุมัติและหลักฐานประกอบสำหรับรายการ Manual Journal ทุกรายการ",
        manual_df,
    )

    # 13. Foreign currency transactions
    fx_df = gl_df[~gl_df["Currency"].str.upper().isin(["THB", "บาท", ""])]
    add_check(
        "DQ-13",
        "Accounting Policy",
        "รายการสกุลเงินตราต่างประเทศ (Foreign Currency)",
        "Warning" if not fx_df.empty else "Pass",
        len(fx_df),
        float(fx_df["Debit"].sum() + fx_df["Credit"].sum()) if not fx_df.empty else 0.0,
        f"พบ {len(fx_df)} รายการที่เป็นสกุลเงินต่างประเทศ: {', '.join(fx_df['Currency'].unique()[:5])}" if not fx_df.empty else "ทุกรายการเป็นสกุลเงิน THB",
        "ตรวจสอบอัตราแลกเปลี่ยน ณ วันเกิดรายการและการปรับมูลค่า (FX Revaluation) ณ วันสิ้นงวด",
        fx_df,
    )

    # 14. Month-end (day 29-31) / Year-end cut-off spike
    valid_dates = gl_df[gl_df["Date"].notna()].copy()
    month_end_df = valid_dates[valid_dates["Date"].dt.day >= 29]
    near_yearend_df = valid_dates[
        (valid_dates["Date"] >= p_end - pd.Timedelta(days=5)) & (valid_dates["Date"] <= p_end)
    ]
    add_check(
        "DQ-14",
        "Cut-off",
        "รายการช่วงปลายเดือน (วันที่ 29–31) และใกล้วันสิ้นงวด",
        "Warning" if not near_yearend_df.empty else "Pass",
        len(month_end_df),
        float(near_yearend_df["Debit"].sum()) if not near_yearend_df.empty else 0.0,
        f"พบ {len(month_end_df)} แถวช่วงวันที่ 29-31 ของเดือน และ {len(near_yearend_df)} แถวในช่วง 5 วันสุดท้ายของงวด",
        "ตรวจสอบ Cut-off รายได้และค่าใช้จ่ายช่วงใกล้วันสิ้นงวดเทียบกับเอกสารส่งมอบ/ตรวจรับ",
        near_yearend_df if not near_yearend_df.empty else month_end_df,
    )

    return pd.DataFrame(checks), details
