from __future__ import annotations

import io
from typing import Any, BinaryIO
import numpy as np
import openpyxl
import pandas as pd


TB_COLUMN_SYNONYMS: dict[str, list[str]] = {
    "account_code": ["account code", "account_code", "acct code", "code", "รหัสบัญชี", "เลขที่บัญชี", "รหัส"],
    "account_name": ["account name", "account_name", "acct name", "name", "description", "ชื่อบัญชี", "รายการ"],
    "opening_balance": ["opening balance", "opening", "beginning balance", "ยอดยกมา", "ยอดต้นงวด"],
    "debit": ["debit", "dr", "เดบิต", "ยอดเดบิต", "ending debit", "เดบิตปลายงวด"],
    "credit": ["credit", "cr", "เครดิต", "ยอดเครดิต", "ending credit", "เครดิตปลายงวด"],
    "balance": ["balance", "ending balance", "net balance", "ยอดคงเหลือ", "ยอดสุทธิ", "คงเหลือ"],
    "prior_balance": ["prior balance", "prior year", "comparative", "ยอดปีก่อน", "ปีก่อน"],
    "department": ["department", "cost center", "แผนก", "ศูนย์ต้นทุน"],
}

GL_COLUMN_SYNONYMS: dict[str, list[str]] = {
    "date": ["date", "posting date", "doc date", "transaction date", "วันที่", "วันที่บันทึก", "วันที่เอกสาร"],
    "doc_no": ["document no", "doc no", "doc_no", "voucher no", "journal no", "je no", "เลขที่เอกสาร", "เลขที่ใบสำคัญ"],
    "account_code": ["account code", "account_code", "acct code", "รหัสบัญชี", "เลขที่บัญชี"],
    "account_name": ["account name", "account_name", "acct name", "ชื่อบัญชี"],
    "debit_account": ["debit account", "dr account", "บัญชีเดบิต"],
    "credit_account": ["credit account", "cr account", "บัญชีเครดิต"],
    "debit": ["debit", "dr", "เดบิต", "จำนวนเงินเดบิต"],
    "credit": ["credit", "cr", "เครดิต", "จำนวนเงินเครดิต"],
    "amount": ["amount", "net amount", "จำนวนเงิน", "ยอดเงิน"],
    "description": ["description", "memo", "narration", "particulars", "รายละเอียด", "คำอธิบาย"],
    "reference": ["reference", "ref", "อ้างอิง", "เลขที่อ้างอิง"],
    "cost_center": ["cost center", "cost_center", "ศูนย์ต้นทุน"],
    "department": ["department", "dept", "แผนก", "หน่วยงาน"],
    "currency": ["currency", "curr", "สกุลเงิน"],
    "entry_type": ["entry type", "journal type", "source", "ประเภท", "ประเภทรายการ"],
    "posted_by": ["posted by", "created by", "user", "ผู้บันทึก"],
}


def list_excel_sheets(file_bytes: bytes) -> list[str]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    sheets = list(wb.sheetnames)
    wb.close()
    return sheets


def read_excel_sheet_raw(file_bytes: bytes, sheet_name: str, header_row: int = 0) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=header_row, dtype=object)
    df = df.dropna(how="all").reset_index(drop=True)
    # Strip whitespace in column names
    df.columns = [str(c).strip() if c is not None else f"Unnamed_{i}" for i, c in enumerate(df.columns)]
    return df


def auto_detect_columns(columns: list[str], synonyms: dict[str, list[str]]) -> dict[str, str | None]:
    detected: dict[str, str | None] = {k: None for k in synonyms}
    normalized_cols = {c: str(c).strip().lower().replace("_", " ") for c in columns}

    for field, candidates in synonyms.items():
        # Exact match first
        for col, norm in normalized_cols.items():
            if norm in candidates:
                detected[field] = col
                break
        if detected[field] is not None:
            continue
        # Substring match fallback
        for col, norm in normalized_cols.items():
            if any(cand in norm for cand in candidates):
                detected[field] = col
                break
    return detected


def _to_numeric(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .replace({"": "0", "nan": "0", "None": "0", "-": "0", "—": "0"})
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def normalize_tb(
    raw_df: pd.DataFrame,
    col_map: dict[str, str | None],
    source_file: str,
    source_sheet: str,
    header_row_1based: int = 1,
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize Trial Balance preserving full source row traceability."""
    errors: list[str] = []
    if not col_map.get("account_code") or not col_map.get("account_name"):
        errors.append("ไม่พบคอลัมน์บังคับของ TB: กรุณาระบุคอลัมน์ 'รหัสบัญชี (Account Code)' และ 'ชื่อบัญชี (Account Name)'")
    has_dr_cr = bool(col_map.get("debit")) and bool(col_map.get("credit"))
    has_bal = bool(col_map.get("balance"))
    if not has_dr_cr and not has_bal:
        errors.append("ไม่พบคอลัมน์ตัวเลขของ TB: กรุณาระบุ ('Debit' และ 'Credit') หรือ 'Balance'")

    if errors:
        return pd.DataFrame(), errors

    df = raw_df.copy()
    # Exact 1-based Excel row index assuming header is header_row_1based
    df["Source_File"] = source_file
    df["Source_Sheet"] = source_sheet
    df["Source_Row"] = [header_row_1based + 1 + i for i in range(len(df))]

    df["Account_Code"] = df[col_map["account_code"]].astype(str).str.strip()
    df["Account_Name"] = df[col_map["account_name"]].astype(str).str.strip()

    # Remove blank or subtotal rows that lack account code or look like grand total rows
    mask_valid = (
        df["Account_Code"].ne("")
        & df["Account_Code"].ne("nan")
        & df["Account_Code"].ne("None")
        & ~df["Account_Code"].str.lower().isin(["total", "grand total", "รวม", "รวมทั้งสิ้น"])
        & ~df["Account_Name"].str.lower().isin(["total", "grand total", "รวม", "รวมทั้งสิ้น"])
    )
    df = df.loc[mask_valid].copy().reset_index(drop=True)

    df["Opening_Balance"] = _to_numeric(df[col_map["opening_balance"]]) if col_map.get("opening_balance") else 0.0
    if has_dr_cr:
        df["Debit"] = _to_numeric(df[col_map["debit"]])
        df["Credit"] = _to_numeric(df[col_map["credit"]])
        if has_bal:
            df["Provided_Balance"] = _to_numeric(df[col_map["balance"]])
        else:
            df["Provided_Balance"] = df["Debit"] - df["Credit"]
    else:
        bal = _to_numeric(df[col_map["balance"]])
        df["Debit"] = np.where(bal >= 0, bal, 0.0)
        df["Credit"] = np.where(bal < 0, -bal, 0.0)
        df["Provided_Balance"] = bal

    df["Net_Balance"] = df["Debit"] - df["Credit"]
    df["Prior_Balance"] = _to_numeric(df[col_map["prior_balance"]]) if col_map.get("prior_balance") else 0.0
    df["Department"] = df[col_map["department"]].astype(str).str.strip() if col_map.get("department") else ""

    cols_order = [
        "Source_File",
        "Source_Sheet",
        "Source_Row",
        "Account_Code",
        "Account_Name",
        "Department",
        "Opening_Balance",
        "Debit",
        "Credit",
        "Net_Balance",
        "Provided_Balance",
        "Prior_Balance",
    ]
    return df[cols_order], []


def normalize_gl(
    raw_df: pd.DataFrame,
    col_map: dict[str, str | None],
    source_file: str,
    source_sheet: str,
    header_row_1based: int = 1,
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize General Ledger supporting both standard Dr/Cr rows and Debit Account / Credit Account / Amount format."""
    errors: list[str] = []
    if not col_map.get("date"):
        errors.append("ไม่พบคอลัมน์วันที่ (Date / วันที่) ในไฟล์ GL")
    if not col_map.get("doc_no"):
        errors.append("ไม่พบคอลัมน์เลขที่เอกสาร (Document No / เลขที่เอกสาร) ในไฟล์ GL")

    standard_mode = bool(col_map.get("account_code")) and (
        (bool(col_map.get("debit")) and bool(col_map.get("credit"))) or bool(col_map.get("amount"))
    )
    pair_mode = bool(col_map.get("debit_account")) and bool(col_map.get("credit_account")) and bool(col_map.get("amount"))

    if not standard_mode and not pair_mode:
        errors.append(
            "ไม่พบคอลัมน์บัญชีและจำนวนเงินใน GL: ต้องมี (Account Code + Debit/Credit หรือ Amount) หรือ (Debit Account + Credit Account + Amount)"
        )

    if errors:
        return pd.DataFrame(), errors

    df = raw_df.copy()
    df["Source_File"] = source_file
    df["Source_Sheet"] = source_sheet
    df["Source_Row"] = [header_row_1based + 1 + i for i in range(len(df))]

    parsed_dates = pd.to_datetime(df[col_map["date"]], errors="coerce")
    doc_series = df[col_map["doc_no"]].astype(str).str.strip().replace({"nan": "", "None": ""})
    desc_series = (
        df[col_map["description"]].astype(str).str.strip().replace({"nan": "", "None": ""})
        if col_map.get("description")
        else pd.Series("", index=df.index)
    )
    ref_series = (
        df[col_map["reference"]].astype(str).str.strip().replace({"nan": "", "None": ""})
        if col_map.get("reference")
        else pd.Series("", index=df.index)
    )
    cc_series = (
        df[col_map["cost_center"]].astype(str).str.strip().replace({"nan": "", "None": ""})
        if col_map.get("cost_center")
        else pd.Series("", index=df.index)
    )
    dept_series = (
        df[col_map["department"]].astype(str).str.strip().replace({"nan": "", "None": ""})
        if col_map.get("department")
        else pd.Series("", index=df.index)
    )
    curr_series = (
        df[col_map["currency"]].astype(str).str.strip().replace({"nan": "THB", "None": "THB", "": "THB"})
        if col_map.get("currency")
        else pd.Series("THB", index=df.index)
    )
    entry_type_series = (
        df[col_map["entry_type"]].astype(str).str.strip().replace({"nan": "Standard", "None": "Standard", "": "Standard"})
        if col_map.get("entry_type")
        else pd.Series("Standard", index=df.index)
    )
    posted_by_series = (
        df[col_map["posted_by"]].astype(str).str.strip().replace({"nan": "", "None": ""})
        if col_map.get("posted_by")
        else pd.Series("", index=df.index)
    )

    if standard_mode:
        out = pd.DataFrame(
            {
                "Source_File": df["Source_File"],
                "Source_Sheet": df["Source_Sheet"],
                "Source_Row": df["Source_Row"],
                "Date": parsed_dates,
                "Doc_No": doc_series,
                "Account_Code": df[col_map["account_code"]].astype(str).str.strip(),
                "Account_Name": (
                    df[col_map["account_name"]].astype(str).str.strip()
                    if col_map.get("account_name")
                    else ""
                ),
                "Description": desc_series,
                "Reference": ref_series,
                "Cost_Center": cc_series,
                "Department": dept_series,
                "Currency": curr_series,
                "Entry_Type": entry_type_series,
                "Posted_By": posted_by_series,
            }
        )
        if col_map.get("debit") and col_map.get("credit"):
            out["Debit"] = _to_numeric(df[col_map["debit"]])
            out["Credit"] = _to_numeric(df[col_map["credit"]])
        else:
            amt = _to_numeric(df[col_map["amount"]])
            out["Debit"] = np.where(amt >= 0, amt, 0.0)
            out["Credit"] = np.where(amt < 0, -amt, 0.0)
    else:
        # Unpivot Debit Account / Credit Account / Amount into balanced 2-line GL rows
        amt = _to_numeric(df[col_map["amount"]])
        rows = []
        for idx in df.index:
            dr_acct = str(df.loc[idx, col_map["debit_account"]]).strip()
            cr_acct = str(df.loc[idx, col_map["credit_account"]]).strip()
            val = float(amt.loc[idx])
            base = {
                "Source_File": df.loc[idx, "Source_File"],
                "Source_Sheet": df.loc[idx, "Source_Sheet"],
                "Source_Row": df.loc[idx, "Source_Row"],
                "Date": parsed_dates.loc[idx],
                "Doc_No": doc_series.loc[idx],
                "Description": desc_series.loc[idx],
                "Reference": ref_series.loc[idx],
                "Cost_Center": cc_series.loc[idx],
                "Department": dept_series.loc[idx],
                "Currency": curr_series.loc[idx],
                "Entry_Type": entry_type_series.loc[idx],
                "Posted_By": posted_by_series.loc[idx],
            }
            if dr_acct and dr_acct not in ("nan", "None"):
                rows.append({**base, "Account_Code": dr_acct, "Account_Name": "", "Debit": val, "Credit": 0.0})
            if cr_acct and cr_acct not in ("nan", "None"):
                rows.append({**base, "Account_Code": cr_acct, "Account_Name": "", "Debit": 0.0, "Credit": val})
        out = pd.DataFrame(rows)

    out = out[out["Account_Code"].ne("") & out["Account_Code"].ne("nan") & out["Account_Code"].ne("None")].copy()
    out["Net_Amount"] = out["Debit"] - out["Credit"]
    out["GL_Ref"] = out.apply(
        lambda r: f"{r['Doc_No']}@{r['Source_Sheet']}:R{r['Source_Row']}",
        axis=1,
    )
    out = out.reset_index(drop=True)
    return out, []


def generate_tb_template_bytes() -> bytes:
    df = pd.DataFrame(
        [
            {"Account Code": "110101", "Account Name": "เงินสดในมือ", "Opening Balance": 50000.0, "Debit": 80000.0, "Credit": 0.0, "Balance": 80000.0, "Prior Balance": 50000.0, "Department": "HQ"},
            {"Account Code": "110201", "Account Name": "เงินฝากธนาคารออมทรัพย์", "Opening Balance": 1200000.0, "Debit": 1850000.0, "Credit": 0.0, "Balance": 1850000.0, "Prior Balance": 1200000.0, "Department": "HQ"},
            {"Account Code": "211101", "Account Name": "เจ้าหนี้การค้า", "Opening Balance": -400000.0, "Debit": 0.0, "Credit": 650000.0, "Balance": -650000.0, "Prior Balance": -400000.0, "Department": "HQ"},
            {"Account Code": "310101", "Account Name": "ทุนที่ออกและชำระแล้ว", "Opening Balance": -850000.0, "Debit": 0.0, "Credit": 1280000.0, "Balance": -1280000.0, "Prior Balance": -850000.0, "Department": "HQ"},
        ]
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Trial_Balance", index=False)
    return buf.getvalue()


def generate_gl_template_bytes() -> bytes:
    df = pd.DataFrame(
        [
            {"Date": "2025-01-15", "Document No": "JV-2025-001", "Account Code": "110201", "Account Name": "เงินฝากธนาคารออมทรัพย์", "Debit": 500000.0, "Credit": 0.0, "Description": "รับชำระค่าสินค้าจากลูกค้า", "Reference": "INV-2025-001", "Cost Center": "CC-01", "Department": "Sales", "Currency": "THB", "Entry Type": "Standard", "Posted By": "Accountant1"},
            {"Date": "2025-01-15", "Document No": "JV-2025-001", "Account Code": "410101", "Account Name": "รายได้จากการขายสินค้า", "Debit": 0.0, "Credit": 500000.0, "Description": "รับชำระค่าสินค้าจากลูกค้า", "Reference": "INV-2025-001", "Cost Center": "CC-01", "Department": "Sales", "Currency": "THB", "Entry Type": "Standard", "Posted By": "Accountant1"},
        ]
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="General_Ledger", index=False)
    return buf.getvalue()
