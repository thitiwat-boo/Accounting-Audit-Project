import io
from pathlib import Path
import sys

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.accounting_rules import compute_adjusted_tb, empty_adjustments_df
from src.audit_tests import build_supplementary_audit_sheets, run_revenue_and_expense_review
from src.auditor_report import build_draft_auditor_report, collect_unresolved_issues
from src.cashflow import build_cash_flow_statement
from src.config_loader import SAMPLE_DIR
from src.exporters import DETAIL_SHEETS, build_accounting_audit_workbook
from src.financial_statements import build_financial_statements
from src.loaders import GL_COLUMN_SYNONYMS, TB_COLUMN_SYNONYMS, auto_detect_columns, normalize_gl, normalize_tb
from src.mapping import build_initial_coa_mapping, detect_mapping_conflicts_and_unmapped
from src.notes import build_notes_and_checklist
from src.risk_scoring import build_account_risk_register_and_workpaper
from src.models import EntitySetup
from src.validators import run_data_quality_checks


def test_full_excel_export_has_all_sheets_and_valid_formulas():
    setup = EntitySetup(framework_confirmed=True)
    raw_tb = pd.read_excel(SAMPLE_DIR / "sample_tb.xlsx", sheet_name="Trial_Balance", dtype=object)
    raw_gl = pd.read_excel(SAMPLE_DIR / "sample_gl.xlsx", sheet_name="General_Ledger", dtype=object)
    tb_norm, _ = normalize_tb(raw_tb, auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS), "sample_tb.xlsx", "Trial_Balance", 1)
    gl_norm, _ = normalize_gl(raw_gl, auto_detect_columns(list(raw_gl.columns), GL_COLUMN_SYNONYMS), "sample_gl.xlsx", "General_Ledger", 1)

    dq_df, _ = run_data_quality_checks(tb_norm, gl_norm, setup.period_start, setup.period_end)
    coa = build_initial_coa_mapping(tb_norm, gl_norm, setup.materiality_amount)
    coa["Reviewer_Status"] = "Approved"
    unmapped_df, _ = detect_mapping_conflicts_and_unmapped(coa, tb_norm)
    adj_df = empty_adjustments_df()
    atb = compute_adjusted_tb(tb_norm, adj_df, coa)
    fs_res = build_financial_statements(atb, setup)
    cf_res = build_cash_flow_statement(atb, gl_norm, fs_res, setup)
    notes_idx, notes_drf = build_notes_and_checklist(atb, setup)
    rev_df, exp_df = run_revenue_and_expense_review(atb, gl_norm, coa, setup)
    risk_df, wp_df = build_account_risk_register_and_workpaper(atb, gl_norm, coa, setup)
    supp = build_supplementary_audit_sheets(atb, gl_norm, coa, setup)
    unresolved = collect_unresolved_issues(dq_df, unmapped_df, adj_df, fs_res, notes_idx)
    aud_drf, aud_ref = build_draft_auditor_report(setup, unresolved)

    xlsx_bytes, fname, fchk_df = build_accounting_audit_workbook(
        setup=setup,
        tb_df=tb_norm,
        gl_df=gl_norm,
        dq_df=dq_df,
        mapping_df=coa,
        unmapped_df=unmapped_df,
        adjustments_df=adj_df,
        adjusted_tb=atb,
        prior_extracted_df=pd.DataFrame(),
        prior_review_df=pd.DataFrame(),
        fs_result=fs_res,
        cf_result=cf_res,
        notes_index_df=notes_idx,
        notes_draft_df=notes_drf,
        rev_review_df=rev_df,
        exp_review_df=exp_df,
        risk_reg_df=risk_df,
        workpaper_df=wp_df,
        supp_audit=supp,
        auditor_draft_df=aud_drf,
        auditor_ref_df=aud_ref,
        change_log=[],
    )

    assert fname.endswith(".xlsx")
    assert (fchk_df["Status"] == "Error").sum() == 0

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=False)
    required_core = {
        "README", "Parameters", "Reference_Register", "Presentation_Rule_Engine", "Grouping_Master",
        "Data_Quality", "TB_Original", "GL_Original", "TB_Normalized", "GL_Normalized",
        "COA_Mapping", "Unmapped_Accounts", "Adjusting_Entries", "Adjusted_TB",
        "Prior_Year_Extracted", "Prior_Year_Review",
        "FS_Balance_Sheet", "FS_Income_Statement", "FS_Changes_Equity", "FS_Cash_Flow",
        "Notes_Index", "Notes_Draft", "Revenue_Review", "Expense_Review",
        "Audit_Risk_Register", "Audit_Workpaper", "Confirmation_Request_List",
        "Subsequent_Events", "Related_Party_Check", "Tax_Check",
        "Auditor_Report_Draft", "Auditor_Report_Ref", "Management_Dashboard_Data",
        "Cell_Formula_Map", "Source_Traceability", "Formula_Check", "Change_Log",
    }
    assert required_core.issubset(set(wb.sheetnames))
    assert set(DETAIL_SHEETS).issubset(set(wb.sheetnames))

    # Verify FS_Balance_Sheet and Adjusted_TB contain live Excel formulas
    assert str(wb["Adjusted_TB"]["S2"].value).startswith("=")
    assert str(wb["FS_Balance_Sheet"]["D5"].value).startswith("=")
    assert str(wb["FS_Income_Statement"]["D5"].value).startswith("=")
    assert isinstance(wb["Parameters"]["B12"].value, (int, float))
    wb.close()
