from __future__ import annotations

from typing import Any
import pandas as pd

from thai_accounting_audit_pack.src.config_loader import get_grouping_master


RELATED_PARTY_KEYWORDS = [
    "เกี่ยวข้องกัน",
    "กรรมการ",
    "ผู้ถือหุ้น",
    "บริษัทในเครือ",
    "บริษัทย่อย",
    "บริษัทร่วม",
    "related party",
    "director",
    "intercompany",
    "shareholder",
]

TAX_KEYWORDS = ["ภาษี", "vat", "wht", "หัก ณ ที่จ่าย", "ภ.ง.ด", "tax"]


def suggest_account_mapping(
    account_code: str,
    account_name: str,
    net_balance: float,
    gl_df: pd.DataFrame | None = None,
    hierarchy: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Propose 5-level COA mapping with reasoning and confidence score (never assumed final without user confirmation)."""
    if hierarchy is None:
        hierarchy = get_grouping_master().get("hierarchy", [])

    code_s = str(account_code).strip()
    name_l = str(account_name).strip().lower()
    best_rule: dict[str, Any] | None = None
    best_score = 0
    reasons: list[str] = []

    # Optional GL narration clues
    gl_text = ""
    if gl_df is not None and not gl_df.empty:
        sub_gl = gl_df[gl_df["Account_Code"].astype(str).str.strip() == code_s]
        if not sub_gl.empty:
            gl_text = " ".join(sub_gl["Description"].dropna().astype(str).head(5)).lower()

    for rule in hierarchy:
        score = 0
        rule_reasons: list[str] = []

        # 1. Exact keyword match in account name (strongest signal)
        kw_hits = [kw for kw in rule.get("keywords", []) if kw.lower() in name_l]
        if kw_hits:
            score += 55 + min(15, 5 * len(kw_hits))
            rule_reasons.append(f"ชื่อบัญชีตรงคำสำคัญ: {', '.join(kw_hits[:3])}")

        # 2. Account code prefix match
        prefix_hits = [p for p in rule.get("code_prefixes", []) if code_s.startswith(str(p))]
        if prefix_hits:
            longest = max(len(p) for p in prefix_hits)
            score += 25 + (10 if longest >= 4 else 0)
            rule_reasons.append(f"รหัสบัญชีขึ้นต้นด้วย {prefix_hits[0]}")

        # 3. GL description match
        if gl_text:
            gl_hits = [kw for kw in rule.get("keywords", []) if kw.lower() in gl_text]
            if gl_hits:
                score += 10
                rule_reasons.append(f"คำอธิบาย GL สอดคล้อง: {gl_hits[0]}")

        # 4. Normal balance consistency bonus/penalty
        nb = rule.get("normal_balance", "Debit")
        if abs(net_balance) > 0.01:
            if (nb == "Debit" and net_balance > 0) or (nb == "Credit" and net_balance < 0):
                score += 10
                rule_reasons.append(f"ด้านยอดคงเหลือตรง Normal Balance ({nb})")
            else:
                score -= 10

        if score > best_score:
            best_score = score
            best_rule = rule
            reasons = rule_reasons

    # Fallback by Thai COA first digit (1=Asset, 2=Liability, 3=Equity, 4=Revenue, 5=Expense)
    if best_rule is None or best_score < 35:
        first_digit = code_s[:1] if code_s else ""
        fallback_map = {
            "1": ("Asset", 1, "Debit", "สินทรัพย์หมุนเวียน", "สินทรัพย์หมุนเวียนอื่น", "สินทรัพย์หมุนเวียนอื่น", "FS_Balance_Sheet", "D_Other_Current_Assets", "5", "Operating - Working Capital"),
            "2": ("Liability", -1, "Credit", "หนี้สินหมุนเวียน", "เจ้าหนี้การค้าและเจ้าหนี้อื่น", "เจ้าหนี้การค้าและเจ้าหนี้อื่น", "FS_Balance_Sheet", "D_AP_Trade_Other", "11", "Operating - Working Capital"),
            "3": ("Equity", -1, "Credit", "ส่วนของเจ้าของ", "กำไรสะสม", "กำไรสะสม", "FS_Balance_Sheet", "D_Retained_Earnings", "16", "Financing"),
            "4": ("Revenue", -1, "Credit", "รายได้จากการขายหรือการให้บริการ", "รายได้จากการขายและบริการ", "รายได้จากการขายหรือการให้บริการ", "FS_Income_Statement", "D_Revenue", "17", "Operating - Profit"),
            "5": ("Expense", 1, "Debit", "ค่าใช้จ่ายในการบริหาร", "ค่าใช้จ่ายในการบริหาร", "ค่าใช้จ่ายในการบริหาร", "FS_Income_Statement", "D_Administrative_Expenses", "17", "Operating - Profit"),
        }
        if first_digit in fallback_map:
            at, sign, nb, grp, subg, line, stmt, dsheet, note, cf = fallback_map[first_digit]
            confidence = 55
            return {
                "Account_Type": at,
                "FS_Sign": sign,
                "Normal_Balance": nb,
                "Current_Non_Current": "Current" if "หมุนเวียน" in grp else ("Non-Current" if "ไม่หมุนเวียน" in grp else "N/A"),
                "Grouping": grp,
                "Sub_Grouping": subg,
                "Financial_Statement": stmt,
                "Statement_Section": grp,
                "FS_Line_Item": line,
                "Detail_Sheet": dsheet,
                "Note_No": note,
                "Cash_Flow_Class": cf,
                "DBD_Line_Item": line,
                "TFAC_Reference": "AI Suggested (กรุณายืนยัน)",
                "Mapping_Method": "AI Suggested",
                "Confidence_Score": confidence,
                "Suggestion_Reason": f"จัดกลุ่มเบื้องต้นจากเลขนำหน้ารหัสบัญชี '{first_digit}' (ไม่พบคำสำคัญเฉพาะเจาะจง)",
                "Reviewer_Status": "ต้องยืนยัน",
            }
        return {
            "Account_Type": "Memo",
            "FS_Sign": 1,
            "Normal_Balance": "Debit" if net_balance >= 0 else "Credit",
            "Current_Non_Current": "N/A",
            "Grouping": "บัญชีพัก บัญชีเบ็ดเตล็ด และบัญชีที่จัดประเภทไม่ได้",
            "Sub_Grouping": "บัญชีพัก/รอตรวจสอบ",
            "Financial_Statement": "Unmapped_Accounts",
            "Statement_Section": "Unmapped",
            "FS_Line_Item": "ยังไม่จัดประเภท",
            "Detail_Sheet": "D_Other_Current_Assets",
            "Note_No": "N/A",
            "Cash_Flow_Class": "Unclassified",
            "DBD_Line_Item": "ยังไม่จัดประเภท",
            "TFAC_Reference": "Unmapped",
            "Mapping_Method": "AI Suggested",
            "Confidence_Score": 20,
            "Suggestion_Reason": "ไม่พบรหัสหรือคำสำคัญที่ตรงกับ Master Grouping — ต้องให้ผู้ทำบัญชีกำหนดเอง",
            "Reviewer_Status": "Unmapped",
        }

    confidence = max(40, min(98, int(best_score)))
    method = "Rule Based" if confidence >= 85 else "AI Suggested"
    grp = best_rule["grouping"]
    cnc = "Current" if "หมุนเวียน" in grp and "ไม่หมุนเวียน" not in grp else ("Non-Current" if "ไม่หมุนเวียน" in grp else "N/A")
    status = "ต้องยืนยัน" if best_rule["account_type"] != "Memo" else "Unmapped"

    return {
        "Account_Type": best_rule["account_type"],
        "FS_Sign": best_rule["fs_sign"],
        "Normal_Balance": best_rule["normal_balance"],
        "Current_Non_Current": cnc,
        "Grouping": grp,
        "Sub_Grouping": best_rule["sub_grouping"],
        "Financial_Statement": best_rule["statement"],
        "Statement_Section": grp,
        "FS_Line_Item": best_rule["fs_line_item"],
        "Detail_Sheet": best_rule["detail_sheet"],
        "Note_No": best_rule["note_no"],
        "Cash_Flow_Class": best_rule["cash_flow_class"],
        "DBD_Line_Item": best_rule["dbd_line_item"],
        "TFAC_Reference": best_rule["tfac_ref"],
        "Mapping_Method": method,
        "Confidence_Score": confidence,
        "Suggestion_Reason": "; ".join(reasons) if reasons else "ตรงตามเกณฑ์ Master Grouping",
        "Reviewer_Status": status,
    }


def build_initial_coa_mapping(
    tb_df: pd.DataFrame,
    gl_df: pd.DataFrame | None = None,
    materiality_amount: float = 100_000.0,
    existing_mapping: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Create or refresh COA Mapping table preserving existing user confirmations."""
    if tb_df.empty:
        return pd.DataFrame()

    # Combine unique accounts from TB (and any GL-only accounts flagged clearly)
    tb_agg = (
        tb_df.groupby("Account_Code", as_index=False)
        .agg({"Account_Name": "first", "Net_Balance": "sum"})
    )

    if gl_df is not None and not gl_df.empty:
        tb_codes = set(tb_agg["Account_Code"])
        gl_only = gl_df[~gl_df["Account_Code"].isin(tb_codes)]
        if not gl_only.empty:
            gl_agg = (
                gl_only.groupby("Account_Code", as_index=False)
                .agg({"Account_Name": "first", "Net_Amount": "sum"})
                .rename(columns={"Net_Amount": "Net_Balance"})
            )
            tb_agg = pd.concat([tb_agg, gl_agg], ignore_index=True)

    existing_by_code: dict[str, dict[str, Any]] = {}
    if existing_mapping is not None and not existing_mapping.empty:
        for _, row in existing_mapping.iterrows():
            existing_by_code[str(row["Account_Code"]).strip()] = row.to_dict()

    hierarchy = get_grouping_master().get("hierarchy", [])
    rows: list[dict[str, Any]] = []

    for _, r in tb_agg.iterrows():
        code = str(r["Account_Code"]).strip()
        name = str(r["Account_Name"]).strip()
        net_bal = float(r["Net_Balance"])

        if code in existing_by_code and existing_by_code[code].get("Mapping_Method") == "User Confirmed":
            row_dict = dict(existing_by_code[code])
            row_dict["Account_Name"] = name
            rows.append(row_dict)
            continue

        sug = suggest_account_mapping(code, name, net_bal, gl_df=gl_df, hierarchy=hierarchy)
        name_lower = name.lower()
        is_rp = any(k in name_lower for k in RELATED_PARTY_KEYWORDS)
        is_tax = any(k in name_lower for k in TAX_KEYWORDS)
        is_sig = abs(net_bal) >= materiality_amount

        rows.append(
            {
                "Account_Code": code,
                "Account_Name": name,
                "Normal_Balance": sug["Normal_Balance"],
                "Account_Type": sug["Account_Type"],
                "FS_Sign": sug["FS_Sign"],
                "Current_Non_Current": sug["Current_Non_Current"],
                "Grouping": sug["Grouping"],
                "Sub_Grouping": sug["Sub_Grouping"],
                "Financial_Statement": sug["Financial_Statement"],
                "Statement_Section": sug["Statement_Section"],
                "FS_Line_Item": sug["FS_Line_Item"],
                "Detail_Sheet": sug["Detail_Sheet"],
                "Note_No": sug["Note_No"],
                "Cash_Flow_Class": sug["Cash_Flow_Class"],
                "Tax_Classification": "Tax Related" if is_tax else "Standard",
                "Related_Party_Flag": bool(is_rp),
                "Significant_Account_Flag": bool(is_sig),
                "DBD_Line_Item": sug["DBD_Line_Item"],
                "Mapping_Method": sug["Mapping_Method"],
                "Confidence_Score": sug["Confidence_Score"],
                "Suggestion_Reason": sug["Suggestion_Reason"],
                "Reviewer_Status": sug["Reviewer_Status"],
                "Reviewer_Comment": "",
                "Source_Standard_Ref": sug["TFAC_Reference"],
                "Mapping_Version": "v1.0",
            }
        )

    return pd.DataFrame(rows).sort_values("Account_Code").reset_index(drop=True)


def detect_mapping_conflicts_and_unmapped(mapping_df: pd.DataFrame, tb_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (unmapped_df, conflicts_df) to block final FS issuance until resolved."""
    if mapping_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    tb_bal = tb_df.groupby("Account_Code", as_index=False)["Net_Balance"].sum() if not tb_df.empty else pd.DataFrame(columns=["Account_Code", "Net_Balance"])
    merged = mapping_df.merge(tb_bal, on="Account_Code", how="left")
    merged["Net_Balance"] = merged["Net_Balance"].fillna(0.0)

    unmapped_mask = (
        merged["Reviewer_Status"].isin(["Unmapped", "Rejected"])
        | (merged["Financial_Statement"] == "Unmapped_Accounts")
        | (merged["Grouping"].str.contains("จัดประเภทไม่ได้|บัญชีพัก", na=False))
    )
    unmapped_df = merged[unmapped_mask].copy()

    # Conflicts: abnormal sign vs Normal_Balance (excluding Contra & 0 balance), or duplicate codes
    sign_conflict = (
        (merged["Account_Type"] != "Contra")
        & (merged["Net_Balance"].abs() > 0.01)
        & (
            ((merged["Normal_Balance"] == "Debit") & (merged["Net_Balance"] < -0.01))
            | ((merged["Normal_Balance"] == "Credit") & (merged["Net_Balance"] > 0.01))
        )
    )
    unconfirmed_mask = merged["Reviewer_Status"] != "Approved"
    conflicts_df = merged[sign_conflict | unconfirmed_mask].copy()
    conflicts_df["Conflict_Reason"] = ""
    conflicts_df.loc[sign_conflict, "Conflict_Reason"] += "ยอดคงเหลือกลับด้านกับ Normal Balance; "
    conflicts_df.loc[unconfirmed_mask, "Conflict_Reason"] += "ยังไม่ได้รับการยืนยัน (Approved) จากผู้ทำบัญชี; "

    return unmapped_df, conflicts_df
