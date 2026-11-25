from __future__ import annotations

from datetime import date
from typing import Any
import pandas as pd


ADJUSTMENT_COLUMNS = [
    "JE_Number",
    "JE_Date",
    "Category",
    "Debit_Account",
    "Credit_Account",
    "Amount",
    "Description",
    "Reason",
    "Standard_Policy_Ref",
    "Assumptions",
    "Missing_Info",
    "Prepared_By",
    "Reviewed_By",
    "Status",
    "Supporting_Doc_Ref",
]


def empty_adjustments_df() -> pd.DataFrame:
    return pd.DataFrame(columns=ADJUSTMENT_COLUMNS)


def generate_proposed_adjustments(
    tb_df: pd.DataFrame,
    gl_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
    period_end: date,
) -> pd.DataFrame:
    """Propose closing/adjusting entries based strictly on TB/GL signals. User approval is mandatory."""
    if tb_df.empty or mapping_df.empty:
        return empty_adjustments_df()

    merged = tb_df.merge(
        mapping_df[["Account_Code", "Grouping", "Sub_Grouping", "FS_Line_Item", "Related_Party_Flag"]],
        on="Account_Code",
        how="left",
    )
    proposals: list[dict[str, Any]] = []
    je_seq = 1

    def add_prop(
        category: str,
        dr: str,
        cr: str,
        amt: float,
        desc: str,
        reason: str,
        std_ref: str,
        assumptions: str,
        missing: str,
    ) -> None:
        nonlocal je_seq
        proposals.append(
            {
                "JE_Number": f"AJE-PROP-{je_seq:03d}",
                "JE_Date": str(period_end),
                "Category": category,
                "Debit_Account": dr,
                "Credit_Account": cr,
                "Amount": round(float(amt), 2),
                "Description": desc,
                "Reason": reason,
                "Standard_Policy_Ref": std_ref,
                "Assumptions": assumptions,
                "Missing_Info": missing,
                "Prepared_By": "System Proposal (AI/Rule)",
                "Reviewed_By": "",
                "Status": "Proposed",
                "Supporting_Doc_Ref": "[รอเอกสารประกอบจากฝ่ายบัญชี]",
            }
        )
        je_seq += 1

    # 1. Check PPE vs Depreciation expense / Accumulated Depreciation
    ppe_cost = merged[merged["Sub_Grouping"] == "ที่ดิน อาคารและอุปกรณ์"]
    accum_depr = ppe_cost[ppe_cost["Account_Name"].str.contains("ค่าเสื่อมราคาสะสม|accumulated", case=False, na=False)]
    depr_exp = merged[merged["Account_Name"].str.contains("ค่าเสื่อมราคา|depreciation", case=False, na=False)]
    if not ppe_cost.empty and (depr_exp.empty or depr_exp["Net_Balance"].abs().sum() < 1.0):
        gross_ppe = float(ppe_cost[~ppe_cost.index.isin(accum_depr.index)]["Net_Balance"].sum())
        if gross_ppe > 0:
            est_depr = round(gross_ppe * 0.10, 2)
            depr_code = depr_exp["Account_Code"].iloc[0] if not depr_exp.empty else "531001"
            acc_code = accum_depr["Account_Code"].iloc[0] if not accum_depr.empty else "123901"
            add_prop(
                "Depreciation",
                depr_code,
                acc_code,
                est_depr,
                "ประมาณการค่าเสื่อมราคาประจำงวด (ยังไม่พบการบันทึกค่าเสื่อมใน TB)",
                f"มีสินทรัพย์ถาวรมูลค่าทุน {gross_ppe:,.2f} แต่ยอดค่าเสื่อมราคาในงวดเป็น 0",
                "TFRS for NPAEs บทที่ 10 / TAS 16",
                "สมมติฐานเบื้องต้น 10% ต่อปี (กรุณาแทนที่ด้วยยอดจริงจาก Fixed Asset Register)",
                "ทะเบียนทรัพย์สิน (Fixed Asset Register) และอายุการใช้งานแยกประเภท",
            )

    # 2. Check Accounts Receivable vs Allowance for Doubtful Accounts
    ar_rows = merged[merged["Account_Name"].str.contains("ลูกหนี้การค้า|trade receivable", case=False, na=False)]
    allow_rows = merged[merged["Account_Name"].str.contains("ค่าเผื่อหนี้สงสัย|allowance|expected credit", case=False, na=False)]
    ar_bal = float(ar_rows["Net_Balance"].sum()) if not ar_rows.empty else 0.0
    if ar_bal > 0 and (allow_rows.empty or allow_rows["Net_Balance"].abs().sum() < 1.0):
        add_prop(
            "Allowance for doubtful accounts",
            "532001",
            allow_rows["Account_Code"].iloc[0] if not allow_rows.empty else "112901",
            round(ar_bal * 0.01, 2),
            "พิจารณาตั้งค่าเผื่อหนี้สงสัยจะสูญ / ECL ณ วันสิ้นงวด",
            f"มียอดลูกหนี้การค้าคงเหลือ {ar_bal:,.2f} แต่ยังไม่มีการตั้งค่าเผื่อหนี้สงสัยจะสูญ",
            "TFRS for NPAEs บทที่ 7 / TFRS 9",
            "แสดงตัวอย่าง 1% ของยอดลูกหนี้ (ต้องใช้ AR Aging จริงในการคำนวณ)",
            "ตารางวิเคราะห์อายุลูกหนี้ (AR Aging) ณ วันสิ้นงวด",
        )

    # 3. Check Accrued Audit Fee / Year-end Accrued Expenses
    accrued_rows = merged[merged["Sub_Grouping"] == "ค่าใช้จ่ายค้างจ่าย"]
    if accrued_rows.empty or accrued_rows["Net_Balance"].abs().sum() < 1.0:
        add_prop(
            "Accrued expenses",
            "530001",
            "214001",
            0.0,
            "สอบทานการตั้งค่าใช้จ่ายค้างจ่าย ณ วันสิ้นงวด (เช่น ค่าสอบบัญชี ค่าสาธารณูปโภค โบนัส)",
            "ไม่พบยอดคงเหลือในหมวดค่าใช้จ่ายค้างจ่าย ณ วันสิ้นงวด",
            "TFRS for NPAEs บทที่ 13 / เกณฑ์คงค้าง",
            "ยอดตั้งต้นเป็น 0 เพื่อให้ผู้ทำบัญชีกรอกตามใบแจ้งหนี้/สัญญาจริง",
            "ใบแจ้งหนี้หลังวันสิ้นงวด สัญญาจ้างสอบบัญชี และอนุมัติจ่ายโบนัส",
        )

    # 4. Check Income Tax Provision when pre-tax profit > 0
    rev_amt = float(-merged[merged["Grouping"].isin(["รายได้จากการขายหรือการให้บริการ", "รายได้อื่น"])]["Net_Balance"].sum())
    exp_amt = float(merged[merged["Grouping"].isin(["ต้นทุนขายหรือต้นทุนการให้บริการ", "ค่าใช้จ่ายในการขาย", "ค่าใช้จ่ายในการบริหาร", "ค่าใช้จ่ายทางการเงิน"])]["Net_Balance"].sum())
    tax_rows = merged[merged["Grouping"] == "ภาษีเงินได้"]
    pre_tax = rev_amt - exp_amt
    if pre_tax > 0 and (tax_rows.empty or tax_rows["Net_Balance"].abs().sum() < 1.0):
        est_tax = round(pre_tax * 0.20, 2)
        add_prop(
            "Tax provision",
            tax_rows["Account_Code"].iloc[0] if not tax_rows.empty else "550001",
            "215001",
            est_tax,
            "ประมาณการค่าใช้จ่ายภาษีเงินได้นิติบุคคลประจำงวด (20% เบื้องต้น)",
            f"กำไรก่อนภาษีก่อนปรับปรุง {pre_tax:,.2f} แต่ยังไม่มียอดค่าใช้จ่ายภาษีเงินได้",
            "TFRS for NPAEs บทที่ 16 / ประมวลรัษฎากร",
            "ใช้อัตราภาษี 20% โดยยังไม่รวมรายการปรับปรุงบวกกลับ/หักออกทางภาษี (SME ได้รับยกเว้น/ลดอัตราตามเกณฑ์)",
            "กระดาษทำการคำนวณภาษีเงินได้นิติบุคคล (ภ.ง.ด.50) และสิทธิประโยชน์ทางภาษี",
        )

    # 5. Check Current / Non-Current Borrowing Reclassification
    lt_loans = merged[merged["Sub_Grouping"] == "เงินกู้ยืมระยะยาว"]
    st_loans = merged[merged["Sub_Grouping"] == "เงินกู้ยืมระยะสั้นและส่วนที่ถึงกำหนดภายในหนึ่งปี"]
    if not lt_loans.empty and lt_loans["Net_Balance"].abs().sum() > 0:
        has_current_portion = not st_loans[st_loans["Account_Name"].str.contains("ถึงกำหนด|current portion", case=False, na=False)].empty
        if not has_current_portion:
            lt_code = lt_loans["Account_Code"].iloc[0]
            add_prop(
                "Reclassification between current and non-current",
                lt_code,
                "217001",
                0.0,
                "จัดประเภทย่อยส่วนของเงินกู้ยืมระยะยาวที่ถึงกำหนดชำระภายใน 1 ปี",
                "มียอดเงินกู้ยืมระยะยาวคงเหลือแต่ไม่พบบัญชีส่วนที่ถึงกำหนดชำระภายใน 1 ปีแยกต่างหาก",
                "TFRS for NPAEs บทที่ 4 / TAS 1",
                "ระบุจำนวนเงินต้นที่ครบกำหนดชำระภายใน 12 เดือนข้างหน้าจากตารางผ่อนชำระ",
                "ตารางผ่อนชำระเงินกู้และสัญญาเงินกู้ธนาคาร",
            )

    # 6. Check Related Party reclassification if flag is set
    rp_accts = merged[merged["Related_Party_Flag"] == True]
    if not rp_accts.empty:
        first_rp = rp_accts.iloc[0]
        add_prop(
            "Related-party reclassification",
            str(first_rp["Account_Code"]),
            str(first_rp["Account_Code"]),
            0.0,
            "สอบทานการจัดประเภทและการเปิดเผยรายการบุคคลหรือกิจการที่เกี่ยวข้องกัน",
            f"พบบัญชีที่อาจเกี่ยวข้องกับบุคคล/กิจการที่เกี่ยวข้องกันจำนวน {len(rp_accts)} บัญชี",
            "TFRS for NPAEs / TAS 24",
            "ใช้เพื่อยืนยันการแยกแสดงรายการในหมายเหตุประกอบงบฯ และตรวจสอบยอดระหว่างกัน",
            "รายชื่อกรรมการ ผู้ถือหุ้น และหนังสือยืนยันยอดระหว่างกัน",
        )

    # 7. Check Revenue Cut-off if GL has entries near year-end
    if gl_df is not None and not gl_df.empty and gl_df["Date"].notna().any():
        p_end = pd.Timestamp(period_end)
        rev_codes = set(merged[merged["Grouping"] == "รายได้จากการขายหรือการให้บริการ"]["Account_Code"])
        late_rev = gl_df[
            gl_df["Account_Code"].isin(rev_codes)
            & gl_df["Date"].notna()
            & (gl_df["Date"] >= p_end - pd.Timedelta(days=3))
            & (gl_df["Date"] <= p_end)
        ]
        if not late_rev.empty:
            add_prop(
                "Revenue cut-off",
                str(late_rev["Account_Code"].iloc[0]),
                "212901",
                0.0,
                "สอบทานรายการรายได้ช่วง 3 วันสุดท้ายก่อนสิ้นงวด (Revenue Cut-off)",
                f"พบรายการรายได้จำนวน {len(late_rev)} รายการ มูลค่า {late_rev['Credit'].sum():,.2f} ในช่วง 3 วันสุดท้ายของงวด",
                "TFRS for NPAEs บทที่ 18 / TFRS 15",
                "จำนวนเงินตั้งต้นเป็น 0 จนกว่าจะตรวจพบรายการที่ยังไม่ได้ส่งมอบสินค้า/บริการ",
                "ใบส่งของ (Delivery Order) และใบตรวจรับงานที่มีลายเซ็นลูกค้า",
            )

    return pd.DataFrame(proposals, columns=ADJUSTMENT_COLUMNS)


def compute_adjusted_tb(
    tb_df: pd.DataFrame,
    adjustments_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute Adjusted Trial Balance without mutating TB_Original. Only Approved/Posted JE affect Adjusted TB."""
    if tb_df.empty:
        return pd.DataFrame()

    # Aggregate TB by Account_Code
    base = (
        tb_df.groupby("Account_Code", as_index=False)
        .agg(
            {
                "Account_Name": "first",
                "Opening_Balance": "sum",
                "Debit": "sum",
                "Credit": "sum",
                "Net_Balance": "sum",
                "Prior_Balance": "sum",
            }
        )
    )

    adj_dr: dict[str, float] = {}
    adj_cr: dict[str, float] = {}
    if adjustments_df is not None and not adjustments_df.empty:
        active = adjustments_df[adjustments_df["Status"].isin(["Approved", "Posted"])].copy()
        active["Amount"] = pd.to_numeric(active["Amount"], errors="coerce").fillna(0.0)
        for _, r in active.iterrows():
            amt = float(r["Amount"])
            dr_acct = str(r["Debit_Account"]).strip()
            cr_acct = str(r["Credit_Account"]).strip()
            if dr_acct:
                adj_dr[dr_acct] = adj_dr.get(dr_acct, 0.0) + amt
            if cr_acct:
                adj_cr[cr_acct] = adj_cr.get(cr_acct, 0.0) + amt

    # Ensure any new adjustment account codes appear in Adjusted TB
    all_codes = sorted(set(base["Account_Code"]) | set(adj_dr.keys()) | set(adj_cr.keys()))
    rows = []
    base_lookup = base.set_index("Account_Code").to_dict(orient="index")
    map_lookup = (
        mapping_df.set_index("Account_Code").to_dict(orient="index")
        if mapping_df is not None and not mapping_df.empty
        else {}
    )

    for code in all_codes:
        b = base_lookup.get(
            code,
            {"Account_Name": f"บัญชีปรับปรุงใหม่ ({code})", "Opening_Balance": 0.0, "Debit": 0.0, "Credit": 0.0, "Net_Balance": 0.0, "Prior_Balance": 0.0},
        )
        m = map_lookup.get(code, {})
        d_adj = adj_dr.get(code, 0.0)
        c_adj = adj_cr.get(code, 0.0)
        unadj_net = float(b["Net_Balance"])
        adj_net = unadj_net + d_adj - c_adj
        fs_sign = int(m.get("FS_Sign", 1 if not code.startswith(("2", "3", "4")) else -1))
        rows.append(
            {
                "Account_Code": code,
                "Account_Name": m.get("Account_Name", b["Account_Name"]),
                "Account_Type": m.get("Account_Type", "Memo"),
                "Grouping": m.get("Grouping", "บัญชีพัก บัญชีเบ็ดเตล็ด และบัญชีที่จัดประเภทไม่ได้"),
                "Sub_Grouping": m.get("Sub_Grouping", "บัญชีพัก/รอตรวจสอบ"),
                "FS_Line_Item": m.get("FS_Line_Item", "ยังไม่จัดประเภท"),
                "Detail_Sheet": m.get("Detail_Sheet", "D_Other_Current_Assets"),
                "Note_No": m.get("Note_No", "N/A"),
                "Cash_Flow_Class": m.get("Cash_Flow_Class", "Unclassified"),
                "Unadjusted_Debit": float(b["Debit"]),
                "Unadjusted_Credit": float(b["Credit"]),
                "Unadjusted_Net": unadj_net,
                "Adjustment_Debit": d_adj,
                "Adjustment_Credit": c_adj,
                "Adjusted_Net": adj_net,
                "Adjusted_Debit": adj_net if adj_net > 0 else 0.0,
                "Adjusted_Credit": -adj_net if adj_net < 0 else 0.0,
                "FS_Sign": fs_sign,
                "Adjusted_FS_Amount": adj_net * fs_sign,
                "Prior_Balance": float(b["Prior_Balance"]) * fs_sign,
                "Mapping_Status": m.get("Reviewer_Status", "Unmapped"),
            }
        )

    return pd.DataFrame(rows)
