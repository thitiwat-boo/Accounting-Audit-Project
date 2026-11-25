from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.accounting_rules import compute_adjusted_tb, empty_adjustments_df
from src.cashflow import build_cash_flow_statement
from src.config_loader import SAMPLE_DIR
from src.financial_statements import build_financial_statements
from src.loaders import GL_COLUMN_SYNONYMS, TB_COLUMN_SYNONYMS, auto_detect_columns, normalize_gl, normalize_tb
from src.mapping import build_initial_coa_mapping
from src.models import EntitySetup


def test_financial_statements_reconciliation_and_cashflow():
    setup = EntitySetup(framework_confirmed=True, cashflow_method="ทางอ้อม (Indirect)")
    raw_tb = pd.read_excel(SAMPLE_DIR / "sample_tb.xlsx", sheet_name="Trial_Balance", dtype=object)
    raw_gl = pd.read_excel(SAMPLE_DIR / "sample_gl.xlsx", sheet_name="General_Ledger", dtype=object)
    tb_norm, _ = normalize_tb(raw_tb, auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS), "sample_tb.xlsx", "Trial_Balance", 1)
    gl_norm, _ = normalize_gl(raw_gl, auto_detect_columns(list(raw_gl.columns), GL_COLUMN_SYNONYMS), "sample_gl.xlsx", "General_Ledger", 1)
    coa = build_initial_coa_mapping(tb_norm, gl_norm, setup.materiality_amount)
    coa["Reviewer_Status"] = "Approved"
    atb = compute_adjusted_tb(tb_norm, empty_adjustments_df(), coa)

    # No account lost between normalization and reporting
    assert set(tb_norm["Account_Code"]) == set(atb["Account_Code"])

    fs_res = build_financial_statements(atb, setup)
    rec = fs_res["reconciliations"]
    assert abs(rec["bs_balance_diff"]) < 0.01
    assert rec["unmapped_count"] == 0

    # Net income ties to equity movement
    sce = fs_res["changes_in_equity"]
    sce_end = float(sce.loc[sce["Item"] == "ยอดคงเหลือปลายงวด", "Total_Equity"].iloc[0])
    assert abs(sce_end - rec["total_equity"]) < 0.01

    # Indirect cash flow ending cash reconciles to BS cash!
    cf_res = build_cash_flow_statement(atb, gl_norm, fs_res, setup)
    assert cf_res["status"] == "Draft Generated"
    assert cf_res["reconciled"] is True
    assert abs(cf_res["ending_cash_cf"] - rec["cash_ending"]) < 0.01


def test_cashflow_insufficient_data_guard():
    setup = EntitySetup(framework_confirmed=True, cashflow_method="ทางอ้อม (Indirect)")
    raw_tb = pd.DataFrame(
        [
            {"Account Code": "110101", "Account Name": "เงินสดในมือ", "Debit": 1000.0, "Credit": 0.0, "Prior Balance": 0.0},
            {"Account Code": "310101", "Account Name": "ทุนเรือนหุ้น", "Debit": 0.0, "Credit": 1000.0, "Prior Balance": 0.0},
        ]
    )
    tb_norm, _ = normalize_tb(raw_tb, auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS), "tb.xlsx", "TB", 1)
    coa = build_initial_coa_mapping(tb_norm)
    coa["Reviewer_Status"] = "Approved"
    atb = compute_adjusted_tb(tb_norm, empty_adjustments_df(), coa)
    fs_res = build_financial_statements(atb, setup)

    cf_res = build_cash_flow_statement(atb, pd.DataFrame(), fs_res, setup)
    assert cf_res["status"] == "Insufficient Data"
    assert "ต้องใช้ข้อมูลธนาคาร/รายละเอียดรายการเงินสดเพิ่มเติม" in cf_res["message"]
