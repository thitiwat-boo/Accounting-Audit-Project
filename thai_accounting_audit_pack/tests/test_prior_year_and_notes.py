from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.accounting_rules import compute_adjusted_tb, empty_adjustments_df
from src.config_loader import SAMPLE_DIR
from src.loaders import TB_COLUMN_SYNONYMS, auto_detect_columns, normalize_tb
from src.mapping import build_initial_coa_mapping
from src.models import EntitySetup
from src.notes import build_notes_and_checklist
from src.prior_year import extract_prior_year_excel, extract_prior_year_pdf


def test_prior_year_excel_and_pdf_extraction():
    xlsx_bytes = (SAMPLE_DIR / "sample_prior_year_fs.xlsx").read_bytes()
    df_xl, meta_xl = extract_prior_year_excel(xlsx_bytes, "sample_prior_year_fs.xlsx")
    assert not df_xl.empty
    assert meta_xl["file_type"] == "Excel"
    assert (df_xl["UserConfirmed"] == False).all()

    pdf_bytes = (SAMPLE_DIR / "sample_prior_year_fs.pdf").read_bytes()
    df_pdf, meta_pdf = extract_prior_year_pdf(pdf_bytes, "sample_prior_year_fs.pdf")
    assert not df_pdf.empty
    assert "Page 1" in df_pdf["PriorYearSheetOrPage"].tolist()
    assert df_pdf["PriorYearSourceRowOrBoundingBox"].str.startswith("bbox(").all()


def test_notes_and_disclosure_checklist_placeholders():
    setup = EntitySetup(framework_confirmed=True)
    raw_tb = pd.read_excel(SAMPLE_DIR / "sample_tb.xlsx", sheet_name="Trial_Balance", dtype=object)
    tb_norm, _ = normalize_tb(raw_tb, auto_detect_columns(list(raw_tb.columns), TB_COLUMN_SYNONYMS), "sample_tb.xlsx", "Trial_Balance", 1)
    coa = build_initial_coa_mapping(tb_norm)
    atb = compute_adjusted_tb(tb_norm, empty_adjustments_df(), coa)

    idx_df, drf_df = build_notes_and_checklist(atb, setup)
    assert len(idx_df) >= 23
    assert len(drf_df) >= 23
    assert drf_df["Draft_Text"].str.contains(r"\[รอ", regex=True).any()
