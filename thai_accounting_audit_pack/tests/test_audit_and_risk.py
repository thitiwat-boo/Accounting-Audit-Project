from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.accounting_rules import compute_adjusted_tb, empty_adjustments_df
from src.audit_tests import run_revenue_and_expense_review
from src.auditor_report import OPINION_CHOICES, build_draft_auditor_report, collect_unresolved_issues
from src.config_loader import SAMPLE_DIR
from src.loaders import GL_COLUMN_SYNONYMS, TB_COLUMN_SYNONYMS, auto_detect_columns, normalize_gl, normalize_tb
from src.mapping import build_initial_coa_mapping
from src.models import EntitySetup
from src.risk_scoring import build_account_risk_register_and_workpaper


def test_audit_risk_and_revenue_expense_review():
    setup = EntitySetup(framework_confirmed=True)
    raw_tb = pd.read_excel(SAMPLE_DIR / "sample_tb.xlsx", sheet_name="Trial_Balance", dtype=object)
    raw_gl = pd.read_excel(SAMPLE_DIR / "sample_gl.xlsx", sheet_name="General_Ledger", dtype=object)
    tb_norm, _ = normalize_tb(raw_tb, auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS), "sample_tb.xlsx", "Trial_Balance", 1)
    gl_norm, _ = normalize_gl(raw_gl, auto_detect_columns(list(raw_gl.columns), GL_COLUMN_SYNONYMS), "sample_gl.xlsx", "General_Ledger", 1)
    coa = build_initial_coa_mapping(tb_norm, gl_norm, setup.materiality_amount)
    atb = compute_adjusted_tb(tb_norm, empty_adjustments_df(), coa)

    risk_df, wp_df = build_account_risk_register_and_workpaper(atb, gl_norm, coa, setup)
    assert not risk_df.empty
    assert len(wp_df) == len(atb)
    assert "Suggested Audit Procedure" in wp_df["Proposed_Audit_Procedure"].iloc[0]

    rev_df, exp_df = run_revenue_and_expense_review(atb, gl_norm, coa, setup)
    assert not rev_df.empty
    assert not exp_df.empty
    # Must never claim fraud conclusively
    assert not rev_df["Comment"].str.contains("รับรองว่าทุจริต").any()


def test_auditor_report_draft_never_fabricates_opinion_or_license():
    setup = EntitySetup(framework_confirmed=True)
    unresolved = collect_unresolved_issues(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}, pd.DataFrame())
    draft_df, ref_df = build_draft_auditor_report(setup, unresolved)

    assert not draft_df.empty
    assert not ref_df.empty
    assert (draft_df["Approval_Status"] == "Draft for CPA Review").all()
    op_text = draft_df.loc[draft_df["Paragraph_ID"] == "AR-02", "Generated_Text"].iloc[0]
    assert "ไม่สามารถสรุปความเห็นได้จากข้อมูลในระบบ" in op_text
    sig_text = draft_df.loc[draft_df["Paragraph_ID"] == "AR-99", "Generated_Text"].iloc[0]
    assert "[รอระบุเลขทะเบียน CPA]" in sig_text
