from datetime import date
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config_loader import SAMPLE_DIR
from src.loaders import GL_COLUMN_SYNONYMS, TB_COLUMN_SYNONYMS, auto_detect_columns, normalize_gl, normalize_tb
from src.validators import run_data_quality_checks


def test_sample_tb_and_gl_balance_and_checks():
    raw_tb = pd.read_excel(SAMPLE_DIR / "sample_tb.xlsx", sheet_name="Trial_Balance", dtype=object)
    raw_gl = pd.read_excel(SAMPLE_DIR / "sample_gl.xlsx", sheet_name="General_Ledger", dtype=object)

    tb_map = auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS)
    gl_map = auto_detect_columns(list(raw_gl.columns), GL_COLUMN_SYNONYMS)

    tb_norm, tb_errs = normalize_tb(raw_tb, tb_map, "sample_tb.xlsx", "Trial_Balance", 1)
    gl_norm, gl_errs = normalize_gl(raw_gl, gl_map, "sample_gl.xlsx", "General_Ledger", 1)

    assert not tb_errs
    assert not gl_errs
    assert abs(tb_norm["Debit"].sum() - tb_norm["Credit"].sum()) < 0.01

    dq_df, _ = run_data_quality_checks(tb_norm, gl_norm, date(2025, 1, 1), date(2025, 12, 31))
    assert dq_df.loc[dq_df["Check_ID"] == "DQ-01", "Status"].iloc[0] == "Pass"
    assert dq_df.loc[dq_df["Check_ID"] == "DQ-06", "Status"].iloc[0] == "Pass"
    # Sample GL contains manual journals and year-end entries -> Warning expected
    assert dq_df.loc[dq_df["Check_ID"] == "DQ-12", "Status"].iloc[0] == "Warning"
    assert dq_df.loc[dq_df["Check_ID"] == "DQ-14", "Status"].iloc[0] == "Warning"


def test_duplicate_journal_and_date_cutoff_detection():
    raw_tb = pd.DataFrame(
        [
            {"Account Code": "110101", "Account Name": "เงินสด", "Debit": 1000.0, "Credit": 0.0},
            {"Account Code": "410101", "Account Name": "รายได้ขาย", "Debit": 0.0, "Credit": 1000.0},
        ]
    )
    raw_gl = pd.DataFrame(
        [
            {"Date": "2025-12-30", "Document No": "JV-1", "Account Code": "110101", "Debit": 500.0, "Credit": 0.0, "Description": "Dup"},
            {"Date": "2025-12-30", "Document No": "JV-1", "Account Code": "110101", "Debit": 500.0, "Credit": 0.0, "Description": "Dup"},
            {"Date": "2026-01-05", "Document No": "JV-2", "Account Code": "999999", "Debit": 0.0, "Credit": 200.0, "Description": "Out of period"},
        ]
    )
    tb_norm, _ = normalize_tb(raw_tb, auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS), "tb.xlsx", "TB", 1)
    gl_norm, _ = normalize_gl(raw_gl, auto_detect_columns(list(raw_gl.columns), GL_COLUMN_SYNONYMS), "gl.xlsx", "GL", 1)

    dq_df, _ = run_data_quality_checks(tb_norm, gl_norm, date(2025, 1, 1), date(2025, 12, 31))
    assert dq_df.loc[dq_df["Check_ID"] == "DQ-05", "Status"].iloc[0] == "Error"  # Out-of-period date
    assert dq_df.loc[dq_df["Check_ID"] == "DQ-06", "Status"].iloc[0] == "Error"  # Unbalanced JV
    assert dq_df.loc[dq_df["Check_ID"] == "DQ-07", "Status"].iloc[0] == "Warning"  # Duplicate GL row
    assert dq_df.loc[dq_df["Check_ID"] == "DQ-09", "Status"].iloc[0] == "Error"  # Account 999999 missing in TB
