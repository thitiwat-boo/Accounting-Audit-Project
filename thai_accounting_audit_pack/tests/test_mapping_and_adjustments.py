from datetime import date
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.accounting_rules import ADJUSTMENT_COLUMNS, compute_adjusted_tb
from src.config_loader import SAMPLE_DIR
from src.loaders import GL_COLUMN_SYNONYMS, TB_COLUMN_SYNONYMS, auto_detect_columns, normalize_gl, normalize_tb
from src.mapping import build_initial_coa_mapping, detect_mapping_conflicts_and_unmapped


def test_mapping_completeness_and_unmapped_detection():
    raw_tb = pd.read_excel(SAMPLE_DIR / "sample_tb.xlsx", sheet_name="Trial_Balance", dtype=object)
    raw_gl = pd.read_excel(SAMPLE_DIR / "sample_gl.xlsx", sheet_name="General_Ledger", dtype=object)
    tb_norm, _ = normalize_tb(raw_tb, auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS), "sample_tb.xlsx", "Trial_Balance", 1)
    gl_norm, _ = normalize_gl(raw_gl, auto_detect_columns(list(raw_gl.columns), GL_COLUMN_SYNONYMS), "sample_gl.xlsx", "General_Ledger", 1)

    coa = build_initial_coa_mapping(tb_norm, gl_norm, 100_000.0)
    assert set(tb_norm["Account_Code"]) == set(coa["Account_Code"])

    # Approve all mapped accounts -> zero unmapped, zero conflicts
    coa["Reviewer_Status"] = "Approved"
    coa["Mapping_Method"] = "User Confirmed"
    unmapped, conflicts = detect_mapping_conflicts_and_unmapped(coa, tb_norm)
    assert unmapped.empty
    assert conflicts.empty

    # Add a suspense account -> must appear in unmapped
    susp_tb = pd.concat(
        [
            tb_norm,
            pd.DataFrame(
                [
                    {
                        "Source_File": "tb.xlsx", "Source_Sheet": "TB", "Source_Row": 99,
                        "Account_Code": "999101", "Account_Name": "บัญชีพักรอตรวจสอบ", "Department": "HQ",
                        "Opening_Balance": 0.0, "Debit": 1000.0, "Credit": 0.0, "Net_Balance": 1000.0, "Provided_Balance": 1000.0, "Prior_Balance": 0.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    coa2 = build_initial_coa_mapping(susp_tb, gl_norm, 100_000.0, coa)
    unmapped2, _ = detect_mapping_conflicts_and_unmapped(coa2, susp_tb)
    assert "999101" in set(unmapped2["Account_Code"])


def test_adjusted_tb_debit_equals_credit_and_preserves_original():
    raw_tb = pd.read_excel(SAMPLE_DIR / "sample_tb.xlsx", sheet_name="Trial_Balance", dtype=object)
    tb_norm, _ = normalize_tb(raw_tb, auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS), "sample_tb.xlsx", "Trial_Balance", 1)
    coa = build_initial_coa_mapping(tb_norm)

    adj = pd.DataFrame(
        [
            {
                "JE_Number": "AJE-001", "JE_Date": str(date(2025, 12, 31)), "Category": "Accrued expenses",
                "Debit_Account": "530201", "Credit_Account": "214101", "Amount": 25000.0,
                "Description": "Accrued electricity", "Reason": "Cut-off", "Standard_Policy_Ref": "NPAEs",
                "Assumptions": "", "Missing_Info": "", "Prepared_By": "Acc", "Reviewed_By": "CPA",
                "Status": "Posted", "Supporting_Doc_Ref": "INV-ELEC",
            },
            {
                "JE_Number": "AJE-002", "JE_Date": str(date(2025, 12, 31)), "Category": "Accrued expenses",
                "Debit_Account": "530201", "Credit_Account": "214101", "Amount": 99999.0,
                "Description": "Unapproved proposal", "Reason": "Draft", "Standard_Policy_Ref": "NPAEs",
                "Assumptions": "", "Missing_Info": "", "Prepared_By": "Acc", "Reviewed_By": "",
                "Status": "Proposed", "Supporting_Doc_Ref": "",
            },
        ],
        columns=ADJUSTMENT_COLUMNS,
    )
    orig_sum = float(tb_norm["Debit"].sum())
    atb = compute_adjusted_tb(tb_norm, adj, coa)

    # Original TB untouched
    assert float(tb_norm["Debit"].sum()) == orig_sum
    # Only Posted AJE-001 (25,000) is applied, not Proposed AJE-002
    assert abs(float(atb["Adjustment_Debit"].sum()) - 25000.0) < 0.01
    assert abs(float(atb["Adjustment_Credit"].sum()) - 25000.0) < 0.01
    assert abs(float(atb["Adjusted_Debit"].sum()) - float(atb["Adjusted_Credit"].sum())) < 0.01
