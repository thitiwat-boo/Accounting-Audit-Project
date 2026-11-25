from __future__ import annotations

from datetime import datetime
import io
import re
from typing import Any
import openpyxl
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd

from src.config_loader import (
    get_grouping_master_df,
    get_presentation_rules_df,
    get_reference_register,
)
from src.models import EntitySetup
from src.provenance import verify_workbook_formulas


DETAIL_SHEETS = [
    "D_Cash_Bank",
    "D_AR_Trade_Other",
    "D_Inventory",
    "D_Other_Current_Assets",
    "D_PPE",
    "D_Intangible_Assets",
    "D_Investments",
    "D_AP_Trade_Other",
    "D_Accrued_Expenses",
    "D_Borrowings",
    "D_Lease_Liabilities",
    "D_Tax_Payable",
    "D_Employee_Benefits",
    "D_Provisions",
    "D_Share_Capital",
    "D_Retained_Earnings",
    "D_Revenue",
    "D_Cost_of_Sales_or_Service",
    "D_Selling_Expenses",
    "D_Administrative_Expenses",
    "D_Finance_Cost",
    "D_Income_Tax",
    "D_Other_Income_Expense",
    "D_Cash_Flow_Working",
    "D_Changes_in_Equity",
]

# Styles
FILL_HEADER = PatternFill("solid", fgColor="0F4C81")
FILL_SUBHEADER = PatternFill("solid", fgColor="D9E2EC")
FILL_INPUT = PatternFill("solid", fgColor="EBF8FF")
FILL_CALC = PatternFill("solid", fgColor="F8FAFC")
FILL_TOTAL = PatternFill("solid", fgColor="E2E8F0")
FILL_WARN = PatternFill("solid", fgColor="FEF3C7")
FILL_ERR = PatternFill("solid", fgColor="FEE2E2")
FILL_PASS = PatternFill("solid", fgColor="DCFCE7")

FONT_HEADER = Font(name="Tahoma", size=10, bold=True, color="FFFFFF")
FONT_TITLE = Font(name="Tahoma", size=12, bold=True, color="0F4C81")
FONT_BOLD = Font(name="Tahoma", size=10, bold=True, color="1E293B")
FONT_REGULAR = Font(name="Tahoma", size=10, bold=False, color="1E293B")
FONT_FOOTNOTE = Font(name="Tahoma", size=9, italic=True, color="64748B")

THIN_SIDE = Side(border_style="thin", color="CBD5E1")
DOUBLE_SIDE = Side(border_style="double", color="1E293B")
BORDER_CELL = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
BORDER_TOTAL = Border(top=THIN_SIDE, bottom=DOUBLE_SIDE, left=THIN_SIDE, right=THIN_SIDE)

NUM_FMT = "#,##0.00;(#,##0.00);\"-\""


def _safe_filename_part(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9ก-๙_\-]+", "_", text.strip())
    return cleaned[:40] or "Entity"


def build_export_filename(setup: EntitySetup) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ent = _safe_filename_part(setup.entity_name)
    per = str(setup.period_end)
    return f"{ent}_{per}_Accounting_Audit_Pack_{ts}.xlsx"


def _style_table_sheet(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    header_row: int = 1,
    freeze_cell: str = "A2",
    apply_autofilter: bool = True,
) -> None:
    ws.views.sheetView[0].showGridLines = True
    if freeze_cell:
        ws.freeze_panes = freeze_cell
    max_r = ws.max_row
    max_c = ws.max_column
    if apply_autofilter and max_r >= header_row and max_c >= 1:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(max_c)}{max_r}"

    for c in range(1, max_c + 1):
        cell = ws.cell(row=header_row, column=c)
        cell.fill = FILL_HEADER
        cell.font = FONT_HEADER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER_CELL

    # Auto-fit column widths reasonably
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 10
        for cell in col[:200]:
            val = cell.value
            if val is not None:
                s = str(val)
                if not s.startswith("="):
                    max_len = max(max_len, min(48, len(s) + 3))
        ws.column_dimensions[col_letter].width = max(12, max_len)


def _write_df_to_sheet(
    wb: openpyxl.Workbook,
    sheet_name: str,
    df: pd.DataFrame,
    numeric_cols: set[str] | None = None,
    status_col: str | None = None,
    footnote: str = "DRAFT FOR ACCOUNTANT & CPA REVIEW ONLY — ยังไม่ใช่ฉบับที่ตรวจสอบหรือลงนามแล้ว",
) -> openpyxl.worksheet.worksheet.Worksheet:
    ws = wb.create_sheet(title=sheet_name[:31])
    num_cols = numeric_cols or set()

    if df is None or df.empty:
        ws.cell(row=1, column=1, value="Status / Notice").font = FONT_BOLD
        ws.cell(row=2, column=1, value="ไม่มีข้อมูลหรือยังไม่ได้ประมวลผลในส่วนนี้ (N/A - Insufficient Source Data)")
        _style_table_sheet(ws, header_row=1, freeze_cell="A2", apply_autofilter=False)
        return ws

    headers = list(df.columns)
    for c_idx, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c_idx, value=str(h))

    for r_idx, (_, row) in enumerate(df.iterrows(), start=2):
        for c_idx, h in enumerate(headers, start=1):
            val = row[h]
            if pd.isna(val):
                val = None
            elif hasattr(val, "item"):
                val = val.item()
            elif isinstance(val, pd.Timestamp):
                val = str(val.date())
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = FONT_REGULAR
            cell.border = BORDER_CELL
            if h in num_cols and isinstance(val, (int, float)):
                cell.number_format = NUM_FMT
            if status_col and h == status_col and val is not None:
                sv = str(val)
                if sv in ("Pass", "Approved", "Posted", "Low", "Matched"):
                    cell.fill = FILL_PASS
                elif sv in ("Warning", "Medium", "Proposed", "Needs Review", "ต้องยืนยัน"):
                    cell.fill = FILL_WARN
                elif sv in ("Error", "Critical", "High", "Unmapped", "Rejected"):
                    cell.fill = FILL_ERR

    foot_row = len(df) + 3
    ws.cell(row=foot_row, column=1, value=footnote).font = FONT_FOOTNOTE
    _style_table_sheet(ws, header_row=1, freeze_cell="A2", apply_autofilter=True)
    return ws


def _add_risk_conditional_formatting(ws: openpyxl.worksheet.worksheet.Worksheet, col_letter: str, start_row: int, end_row: int) -> None:
    if end_row < start_row:
        return
    rng = f"{col_letter}{start_row}:{col_letter}{end_row}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Critical"'], fill=FILL_ERR))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"High"'], fill=FILL_ERR))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Medium"'], fill=FILL_WARN))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Low"'], fill=FILL_PASS))


def _configure_print_setup(ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    if ws.max_row >= 1 and ws.max_column >= 1:
        ws.print_area = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"


def build_accounting_audit_workbook(
    setup: EntitySetup,
    tb_df: pd.DataFrame,
    gl_df: pd.DataFrame,
    dq_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
    unmapped_df: pd.DataFrame,
    adjustments_df: pd.DataFrame,
    adjusted_tb: pd.DataFrame,
    prior_extracted_df: pd.DataFrame,
    prior_review_df: pd.DataFrame,
    fs_result: dict[str, Any],
    cf_result: dict[str, Any],
    notes_index_df: pd.DataFrame,
    notes_draft_df: pd.DataFrame,
    rev_review_df: pd.DataFrame,
    exp_review_df: pd.DataFrame,
    risk_reg_df: pd.DataFrame,
    workpaper_df: pd.DataFrame,
    supp_audit: dict[str, pd.DataFrame],
    auditor_draft_df: pd.DataFrame,
    auditor_ref_df: pd.DataFrame,
    change_log: list[dict[str, Any]],
    grouping_version: str = "v1.0",
) -> tuple[bytes, str, pd.DataFrame]:
    """Generate complete formula-driven Excel Audit & FS Pack and run Formula_Check verification."""
    filename = build_export_filename(setup)
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    cell_formula_map: list[dict[str, Any]] = []
    source_trace_rows: list[dict[str, Any]] = []

    def record_cell_ref(
        out_sheet: str,
        out_cell: str,
        formula: str,
        displayed_val: Any,
        src_sheet: str,
        src_ref: str,
        src_acct: str = "",
        gl_ref: str = "",
        adj_ref: str = "",
        map_ref: str = "",
        desc: str = "",
        status: str = "Formula Generated / Review Required",
    ) -> None:
        cell_formula_map.append(
            {
                "OutputFile": filename,
                "OutputSheet": out_sheet,
                "OutputCell": out_cell,
                "Formula": formula,
                "DisplayedValue": displayed_val,
                "SourceSheet": src_sheet,
                "SourceCellOrRow": src_ref,
                "SourceAccountCode": src_acct,
                "SourceGLReference": gl_ref,
                "AdjustmentReference": adj_ref,
                "MappingReference": map_ref,
                "CalculationDescription": desc,
                "ReviewStatus": status,
            }
        )

    # 1. README
    ws_readme = wb.create_sheet("README")
    readme_lines = [
        ("Thai Accounting, Financial Statements & Audit Workpaper Pack", "Draft Version 2.0"),
        ("ข้อกำหนดวิชาชีพ", "เอกสารนี้เป็นฉบับร่างเพื่อประกอบการปิดบัญชีและสอบทานโดยผู้ทำบัญชีและผู้สอบบัญชีรับอนุญาต (CPA) เท่านั้น"),
        ("ห้ามอ้างอิง", "ห้ามอ้างว่าเป็นงบการเงินที่ตรวจสอบแล้วหรือรายงานผู้สอบบัญชีที่ลงนามแล้ว"),
        ("วันที่สร้างไฟล์", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("Mapping Version", grouping_version),
        ("สีในตาราง (Color Legend)", "ฟ้าอ่อน = Input | เทาอ่อน = Calculated/Formula | เหลือง = Warning/Review | แดง = Error/High Risk | เขียว = Pass/Approved"),
    ]
    ws_readme.cell(row=1, column=1, value="หัวข้อ").font = FONT_HEADER
    ws_readme.cell(row=1, column=2, value="รายละเอียด").font = FONT_HEADER
    for idx, (k, v) in enumerate(readme_lines, start=2):
        ws_readme.cell(row=idx, column=1, value=k).font = FONT_BOLD
        ws_readme.cell(row=idx, column=2, value=v).font = FONT_REGULAR
    _style_table_sheet(ws_readme, header_row=1, freeze_cell="A2", apply_autofilter=False)

    # 2. Parameters (B12 is Unit Divisor used by formulas!)
    ws_param = wb.create_sheet("Parameters")
    param_rows = [
        ("Parameter", "Value", "Cell_Type"),
        ("Entity Name", setup.entity_name, "Input"),
        ("Registration No", setup.registration_no or "-", "Input"),
        ("Entity Type", setup.effective_entity_type, "Input"),
        ("Business Type", setup.business_type, "Input"),
        ("Financial Reporting Framework", setup.framework, "Input"),
        ("DBD Presentation Template", setup.dbd_template, "Input"),
        ("Audit Standard Reference", setup.audit_standard_ref, "Input"),
        ("Period Start", str(setup.period_start), "Input"),
        ("Period End", str(setup.period_end), "Input"),
        ("Currency / Display Unit", f"{setup.currency} ({setup.unit_scale})", "Input"),
        ("Unit Divisor", float(setup.unit_divisor), "Input"),  # Row 12 -> Parameters!$B$12
        ("Expense Presentation", setup.expense_presentation, "Input"),
        ("Cash Flow Method", setup.cashflow_method, "Input"),
        ("Materiality (THB)", float(setup.materiality_amount), "Input"),
        ("Mapping Version", grouping_version, "Input"),
        ("Data Lineage Policy", "Adjusted_TB -> Detail Schedules (D_*) -> Financial Statements (FS_*)", "Rule"),
        ("Generated Timestamp", datetime.now().isoformat(timespec="seconds"), "System"),
    ]
    for r_i, (p_k, p_v, p_t) in enumerate(param_rows, start=1):
        c1 = ws_param.cell(row=r_i, column=1, value=p_k)
        c2 = ws_param.cell(row=r_i, column=2, value=p_v)
        c3 = ws_param.cell(row=r_i, column=3, value=p_t)
        if r_i > 1:
            c1.font = FONT_BOLD
            c2.font = FONT_REGULAR
            c3.font = FONT_REGULAR
            c2.fill = FILL_INPUT if p_t == "Input" else FILL_CALC
            if isinstance(p_v, float):
                c2.number_format = NUM_FMT
    _style_table_sheet(ws_param, header_row=1, freeze_cell="A2", apply_autofilter=False)

    # 3. Reference_Register, Presentation_Rule_Engine, Grouping_Master
    reg = get_reference_register()
    reg_df = pd.DataFrame(reg.get("tfac_standards", []) + reg.get("dbd_references", []))
    _write_df_to_sheet(wb, "Reference_Register", reg_df)
    _write_df_to_sheet(wb, "Presentation_Rule_Engine", get_presentation_rules_df())
    _write_df_to_sheet(wb, "Grouping_Master", get_grouping_master_df())

    # 4. Data_Quality
    _write_df_to_sheet(wb, "Data_Quality", dq_df, numeric_cols={"Issue_Count", "Impact_Amount"}, status_col="Status")

    # 5. TB_Original & GL_Original
    _write_df_to_sheet(wb, "TB_Original", tb_df, numeric_cols={"Opening_Balance", "Debit", "Credit", "Net_Balance", "Provided_Balance", "Prior_Balance"})
    _write_df_to_sheet(wb, "GL_Original", gl_df, numeric_cols={"Debit", "Credit", "Net_Amount"})

    # 6. TB_Normalized (with real Excel Net_Balance formula =H{r}-I{r})
    ws_tbn = wb.create_sheet("TB_Normalized")
    tbn_headers = ["Source_File", "Source_Sheet", "Source_Row", "Account_Code", "Account_Name", "Department", "Opening_Balance", "Debit", "Credit", "Net_Balance", "Provided_Balance", "Prior_Balance"]
    for c_i, h in enumerate(tbn_headers, start=1):
        ws_tbn.cell(row=1, column=c_i, value=h)
    for r_i, (_, r) in enumerate(tb_df.iterrows(), start=2):
        vals = [r["Source_File"], r["Source_Sheet"], int(r["Source_Row"]), str(r["Account_Code"]), str(r["Account_Name"]), str(r.get("Department", "")), float(r["Opening_Balance"]), float(r["Debit"]), float(r["Credit"]), f"=H{r_i}-I{r_i}", float(r["Provided_Balance"]), float(r["Prior_Balance"])]
        for c_i, v in enumerate(vals, start=1):
            cell = ws_tbn.cell(row=r_i, column=c_i, value=v)
            cell.border = BORDER_CELL
            cell.font = FONT_REGULAR
            if c_i >= 7:
                cell.number_format = NUM_FMT
                cell.fill = FILL_CALC if c_i == 10 else FILL_INPUT
        source_trace_rows.append({"Target_Sheet": "TB_Normalized", "Target_Row": r_i, "Account_Code": str(r["Account_Code"]), "Source_File": r["Source_File"], "Source_Sheet": r["Source_Sheet"], "Source_Row": int(r["Source_Row"])})
    _style_table_sheet(ws_tbn, header_row=1, freeze_cell="A2")

    # 7. GL_Normalized (with real Excel Net_Amount formula =M{r}-N{r})
    ws_gln = wb.create_sheet("GL_Normalized")
    gln_headers = ["Source_File", "Source_Sheet", "Source_Row", "Date", "Doc_No", "Account_Code", "Account_Name", "Description", "Reference", "Cost_Center", "Department", "Currency", "Debit", "Credit", "Net_Amount", "Entry_Type", "Posted_By", "GL_Ref"]
    for c_i, h in enumerate(gln_headers, start=1):
        ws_gln.cell(row=1, column=c_i, value=h)
    if not gl_df.empty:
        for r_i, (_, r) in enumerate(gl_df.iterrows(), start=2):
            dt_val = str(r["Date"].date()) if pd.notna(r["Date"]) else ""
            vals = [r["Source_File"], r["Source_Sheet"], int(r["Source_Row"]), dt_val, str(r["Doc_No"]), str(r["Account_Code"]), str(r["Account_Name"]), str(r["Description"]), str(r["Reference"]), str(r["Cost_Center"]), str(r["Department"]), str(r["Currency"]), float(r["Debit"]), float(r["Credit"]), f"=M{r_i}-N{r_i}", str(r["Entry_Type"]), str(r["Posted_By"]), str(r["GL_Ref"])]
            for c_i, v in enumerate(vals, start=1):
                cell = ws_gln.cell(row=r_i, column=c_i, value=v)
                cell.border = BORDER_CELL
                cell.font = FONT_REGULAR
                if c_i in (13, 14, 15):
                    cell.number_format = NUM_FMT
                    cell.fill = FILL_CALC if c_i == 15 else FILL_INPUT
    _style_table_sheet(ws_gln, header_row=1, freeze_cell="A2")

    # 8. COA_Mapping & Unmapped_Accounts
    _write_df_to_sheet(wb, "COA_Mapping", mapping_df, numeric_cols={"FS_Sign", "Confidence_Score"}, status_col="Reviewer_Status")
    _write_df_to_sheet(wb, "Unmapped_Accounts", unmapped_df, numeric_cols={"Net_Balance"}, status_col="Reviewer_Status")

    # 9. Adjusting_Entries (Unlocked/Input style)
    _write_df_to_sheet(wb, "Adjusting_Entries", adjustments_df, numeric_cols={"Amount"}, status_col="Status")

    # 10. Adjusted_TB (100% Formula-driven from TB_Normalized + Adjusting_Entries!)
    ws_atb = wb.create_sheet("Adjusted_TB")
    atb_headers = [
        "Account_Code", "Account_Name", "Account_Type", "Grouping", "Sub_Grouping",
        "FS_Line_Item", "Detail_Sheet", "Note_No", "Cash_Flow_Class",
        "Unadjusted_Debit", "Unadjusted_Credit", "Unadjusted_Net",
        "Adjustment_Debit", "Adjustment_Credit", "Adjusted_Net",
        "Adjusted_Debit", "Adjusted_Credit", "FS_Sign",
        "Adjusted_FS_Amount", "Prior_Balance", "Mapping_Status",
    ]
    for c_i, h in enumerate(atb_headers, start=1):
        ws_atb.cell(row=1, column=c_i, value=h)

    for r_i, (_, r) in enumerate(adjusted_tb.iterrows(), start=2):
        code = str(r["Account_Code"])
        f_udr = f'=SUMIFS(TB_Normalized!$H:$H,TB_Normalized!$D:$D,$A{r_i})'
        f_ucr = f'=SUMIFS(TB_Normalized!$I:$I,TB_Normalized!$D:$D,$A{r_i})'
        f_unet = f'=SUMIFS(TB_Normalized!$J:$J,TB_Normalized!$D:$D,$A{r_i})'
        f_adr = f'=SUMIFS(Adjusting_Entries!$F:$F,Adjusting_Entries!$D:$D,$A{r_i},Adjusting_Entries!$N:$N,"Posted")+SUMIFS(Adjusting_Entries!$F:$F,Adjusting_Entries!$D:$D,$A{r_i},Adjusting_Entries!$N:$N,"Approved")'
        f_acr = f'=SUMIFS(Adjusting_Entries!$F:$F,Adjusting_Entries!$E:$E,$A{r_i},Adjusting_Entries!$N:$N,"Posted")+SUMIFS(Adjusting_Entries!$F:$F,Adjusting_Entries!$E:$E,$A{r_i},Adjusting_Entries!$N:$N,"Approved")'
        f_anet = f"=L{r_i}+M{r_i}-N{r_i}"
        f_adr_net = f"=IF(O{r_i}>0,O{r_i},0)"
        f_acr_net = f"=IF(O{r_i}<0,-O{r_i},0)"
        f_fs_amt = f"=O{r_i}*R{r_i}"

        vals = [
            code, str(r["Account_Name"]), str(r["Account_Type"]), str(r["Grouping"]), str(r["Sub_Grouping"]),
            str(r["FS_Line_Item"]), str(r["Detail_Sheet"]), str(r["Note_No"]), str(r["Cash_Flow_Class"]),
            f_udr, f_ucr, f_unet, f_adr, f_acr, f_anet, f_adr_net, f_acr_net, int(r["FS_Sign"]),
            f_fs_amt, float(r.get("Prior_Balance", 0.0)), str(r.get("Mapping_Status", "")),
        ]
        for c_i, v in enumerate(vals, start=1):
            cell = ws_atb.cell(row=r_i, column=c_i, value=v)
            cell.border = BORDER_CELL
            cell.font = FONT_REGULAR
            if 10 <= c_i <= 20 and c_i != 18:
                cell.number_format = NUM_FMT
                if isinstance(v, str) and v.startswith("="):
                    cell.fill = FILL_CALC
        record_cell_ref("Adjusted_TB", f"S{r_i}", f_fs_amt, float(r["Adjusted_FS_Amount"]), "TB_Normalized", f"Account {code}", code, "", "", str(r["FS_Line_Item"]), "Adjusted FS Amount = Adjusted_Net * FS_Sign")

    if not adjusted_tb.empty:
        tot_r = len(adjusted_tb) + 2
        ws_atb.cell(row=tot_r, column=1, value="TOTAL").font = FONT_BOLD
        for c_i in [10, 11, 12, 13, 14, 15, 16, 17]:
            col_l = get_column_letter(c_i)
            c = ws_atb.cell(row=tot_r, column=c_i, value=f"=SUM({col_l}2:{col_l}{tot_r-1})")
            c.font = FONT_BOLD
            c.fill = FILL_TOTAL
            c.border = BORDER_TOTAL
            c.number_format = NUM_FMT
    _style_table_sheet(ws_atb, header_row=1, freeze_cell="A2")

    # 11. Prior Year sheets
    _write_df_to_sheet(wb, "Prior_Year_Extracted", prior_extracted_df, numeric_cols={"ExtractedAmount", "Confidence"})
    _write_df_to_sheet(wb, "Prior_Year_Review", prior_review_df, numeric_cols={"ExtractedAmount", "TB_Opening_or_Prior", "Difference", "Confidence"}, status_col="Status")

    # 12. 25 Detail Schedules (D_*) - Formula-driven!
    detail_totals_map: dict[str, dict[str, Any]] = {}
    risk_by_acct = risk_reg_df.set_index("Account_Code")["Risk_Level"].to_dict() if not risk_reg_df.empty else {}
    d_headers = [
        "Line No", "Account Code", "Account Name", "Grouping", "Sub Grouping", "FS Line Item",
        "Current Year Formula", "Current Year Amount", "Prior Year Formula", "Prior Year Amount",
        "TB/GL Ref", "Note No.", "Audit Risk", "Review Status", "Reviewer Comment",
    ]
    for d_name in DETAIL_SHEETS:
        ws_d = wb.create_sheet(d_name[:31])
        ws_d.cell(row=1, column=1, value=f"{setup.entity_name} — Detail Schedule: {d_name}").font = FONT_TITLE
        ws_d.cell(row=2, column=1, value=f"Period End: {setup.period_end} | Unit: {setup.currency} ({setup.unit_scale}) | Draft for Review").font = FONT_FOOTNOTE

        for c_i, h in enumerate(d_headers, start=1):
            ws_d.cell(row=4, column=c_i, value=h)

        sub = adjusted_tb[adjusted_tb["Detail_Sheet"] == d_name].copy() if not adjusted_tb.empty else pd.DataFrame()
        if sub.empty:
            # Row 5 placeholder total = 0 formula so FS links never break!
            ws_d.cell(row=5, column=1, value=1)
            ws_d.cell(row=5, column=2, value="-")
            ws_d.cell(row=5, column=3, value="ไม่มีรายการบัญชีที่จัดเข้าหมวดนี้")
            ws_d.cell(row=5, column=7, value="=0")
            c_cy = ws_d.cell(row=5, column=8, value="=0")
            c_cy.number_format = NUM_FMT
            ws_d.cell(row=5, column=9, value="=0")
            c_py = ws_d.cell(row=5, column=10, value="=0")
            c_py.number_format = NUM_FMT

            tot_r = 6
            ws_d.cell(row=tot_r, column=3, value="TOTAL").font = FONT_BOLD
            c_tot_cy = ws_d.cell(row=tot_r, column=8, value="=SUM(H5:H5)")
            c_tot_py = ws_d.cell(row=tot_r, column=10, value="=SUM(J5:J5)")
            c_tot_cy.font = FONT_BOLD
            c_tot_py.font = FONT_BOLD
            c_tot_cy.fill = FILL_TOTAL
            c_tot_py.fill = FILL_TOTAL
            c_tot_cy.border = BORDER_TOTAL
            c_tot_py.border = BORDER_TOTAL
            c_tot_cy.number_format = NUM_FMT
            c_tot_py.number_format = NUM_FMT
            detail_totals_map[d_name] = {"start_row": 5, "end_row": 5, "total_row": tot_r, "cy_val": 0.0, "py_val": 0.0}
        else:
            for idx_row, (_, r) in enumerate(sub.iterrows(), start=1):
                r_i = 4 + idx_row
                code = str(r["Account_Code"])
                f_cy = f"=SUMIFS(Adjusted_TB!$S:$S,Adjusted_TB!$A:$A,$B{r_i})/Parameters!$B$12"
                f_py = f"=SUMIFS(Adjusted_TB!$T:$T,Adjusted_TB!$A:$A,$B{r_i})/Parameters!$B$12"
                cy_val = float(r["Adjusted_FS_Amount"]) / setup.unit_divisor
                py_val = float(r.get("Prior_Balance", 0.0)) / setup.unit_divisor

                row_vals = [
                    idx_row, code, str(r["Account_Name"]), str(r["Grouping"]), str(r["Sub_Grouping"]), str(r["FS_Line_Item"]),
                    f"'{f_cy}", f_cy, f"'{f_py}", f_py,
                    f"TB_Normalized ({code})", str(r["Note_No"]), risk_by_acct.get(code, "Low"), str(r["Mapping_Status"]), "",
                ]
                for c_i, v in enumerate(row_vals, start=1):
                    cell = ws_d.cell(row=r_i, column=c_i, value=v)
                    cell.border = BORDER_CELL
                    cell.font = FONT_REGULAR
                    if c_i in (8, 10):
                        cell.number_format = NUM_FMT
                        cell.fill = FILL_CALC
                record_cell_ref(d_name, f"H{r_i}", f_cy, cy_val, "Adjusted_TB", f"Account {code}", code, "", "", str(r["FS_Line_Item"]), "Detail schedule line linked to Adjusted_TB")

            end_r = 4 + len(sub)
            tot_r = end_r + 1
            ws_d.cell(row=tot_r, column=3, value="TOTAL").font = FONT_BOLD
            f_tot_cy = f"=SUM(H5:H{end_r})"
            f_tot_py = f"=SUM(J5:J{end_r})"
            c_tot_cy = ws_d.cell(row=tot_r, column=8, value=f_tot_cy)
            c_tot_py = ws_d.cell(row=tot_r, column=10, value=f_tot_py)
            c_tot_cy.font = FONT_BOLD
            c_tot_py.font = FONT_BOLD
            c_tot_cy.fill = FILL_TOTAL
            c_tot_py.fill = FILL_TOTAL
            c_tot_cy.border = BORDER_TOTAL
            c_tot_py.border = BORDER_TOTAL
            c_tot_cy.number_format = NUM_FMT
            c_tot_py.number_format = NUM_FMT
            detail_totals_map[d_name] = {
                "start_row": 5,
                "end_row": end_r,
                "total_row": tot_r,
                "cy_val": float(sub["Adjusted_FS_Amount"].sum()) / setup.unit_divisor,
                "py_val": float(sub["Prior_Balance"].sum()) / setup.unit_divisor,
            }

        _style_table_sheet(ws_d, header_row=4, freeze_cell="A5")
        _add_risk_conditional_formatting(ws_d, "M", 5, max(5, ws_d.max_row - 1))

    # Helper to create Excel formula linking FS line item to its Detail Sheet!
    def fs_detail_formula(detail_sheet: str, fs_line_item: str, col_char: str = "H", negate: bool = False) -> str:
        info = detail_totals_map[detail_sheet]
        # Shared detail sheets (multiple FS line items in same D_* sheet) use SUMIFS on D_*!
        if detail_sheet in ("D_Borrowings", "D_Other_Income_Expense"):
            expr = f'SUMIFS({detail_sheet}!${col_char}$5:${col_char}${info["end_row"]},{detail_sheet}!$F$5:$F${info["end_row"]},"{fs_line_item}")'
        else:
            expr = f"{detail_sheet}!{col_char}{info['total_row']}"
        return f"=-({expr})" if negate else f"={expr}"

    # 13. FS_Income_Statement (with live Excel formulas!)
    ws_is = wb.create_sheet("FS_Income_Statement")
    ws_is.cell(row=1, column=1, value=f"{setup.entity_name} — งบกำไรขาดทุน (ฉบับร่าง)").font = FONT_TITLE
    ws_is.cell(row=2, column=1, value=f"สำหรับงวดสิ้นสุด {setup.period_end} | หน่วย: {setup.currency} ({setup.unit_scale}) | กรอบ: {setup.framework}").font = FONT_FOOTNOTE
    is_headers = ["หมวด", "รายการ", "หมายเหตุ", "งวดปัจจุบัน (Formula)", "งวดเปรียบเทียบ (Formula)", "สูตรอ้างอิง", "แหล่งข้อมูลต้นทาง"]
    for c_i, h in enumerate(is_headers, start=1):
        ws_is.cell(row=4, column=c_i, value=h)

    is_df = fs_result.get("income_statement", pd.DataFrame())
    is_row_map: dict[str, int] = {}
    net_income_row = 5
    # Map line items directly to exact Excel formulas
    for idx_r, (_, r) in enumerate(is_df.iterrows(), start=5):
        line_name = str(r["Line_Item"])
        is_row_map[line_name] = idx_r
        if "รายได้จากการขาย" in line_name:
            f_cy = fs_detail_formula("D_Revenue", "รายได้จากการขายหรือการให้บริการ", "H")
            f_py = fs_detail_formula("D_Revenue", "รายได้จากการขายหรือการให้บริการ", "J")
        elif "ต้นทุนขาย" in line_name:
            f_cy = fs_detail_formula("D_Cost_of_Sales_or_Service", "ต้นทุนขายหรือต้นทุนการให้บริการ", "H", negate=True)
            f_py = fs_detail_formula("D_Cost_of_Sales_or_Service", "ต้นทุนขายหรือต้นทุนการให้บริการ", "J", negate=True)
        elif "กำไร (ขาดทุน) ขั้นต้น" in line_name:
            r_rev = is_row_map["รายได้จากการขายหรือการให้บริการ"]
            r_cog = is_row_map["หัก ต้นทุนขายหรือต้นทุนการให้บริการ"]
            f_cy = f"=D{r_rev}+D{r_cog}"
            f_py = f"=E{r_rev}+E{r_cog}"
        elif "รายได้อื่น" in line_name:
            f_cy = fs_detail_formula("D_Other_Income_Expense", "รายได้อื่น", "H")
            f_py = fs_detail_formula("D_Other_Income_Expense", "รายได้อื่น", "J")
        elif "ค่าใช้จ่ายในการขาย" in line_name:
            f_cy = fs_detail_formula("D_Selling_Expenses", "ค่าใช้จ่ายในการขาย", "H", negate=True)
            f_py = fs_detail_formula("D_Selling_Expenses", "ค่าใช้จ่ายในการขาย", "J", negate=True)
        elif "ค่าใช้จ่ายในการบริหาร" in line_name:
            f_cy = fs_detail_formula("D_Administrative_Expenses", "ค่าใช้จ่ายในการบริหาร", "H", negate=True)
            f_py = fs_detail_formula("D_Administrative_Expenses", "ค่าใช้จ่ายในการบริหาร", "J", negate=True)
        elif "ค่าใช้จ่ายอื่น" in line_name:
            f_cy = fs_detail_formula("D_Other_Income_Expense", "ค่าใช้จ่ายอื่น / รายการรอตรวจสอบ", "H", negate=True)
            f_py = fs_detail_formula("D_Other_Income_Expense", "ค่าใช้จ่ายอื่น / รายการรอตรวจสอบ", "J", negate=True)
        elif "EBIT" in line_name:
            gp_r = is_row_map["กำไร (ขาดทุน) ขั้นต้น"]
            f_cy = f"=SUM(D{gp_r}:D{idx_r-1})"
            f_py = f"=SUM(E{gp_r}:E{idx_r-1})"
        elif "ต้นทุนทางการเงิน" in line_name:
            f_cy = fs_detail_formula("D_Finance_Cost", "ต้นทุนทางการเงิน", "H", negate=True)
            f_py = fs_detail_formula("D_Finance_Cost", "ต้นทุนทางการเงิน", "J", negate=True)
        elif "ก่อนค่าใช้จ่ายภาษีเงินได้" in line_name:
            ebit_r = is_row_map["กำไร (ขาดทุน) ก่อนต้นทุนทางการเงินและภาษีเงินได้ (EBIT)"]
            fin_r = is_row_map["หัก ต้นทุนทางการเงิน"]
            f_cy = f"=D{ebit_r}+D{fin_r}"
            f_py = f"=E{ebit_r}+E{fin_r}"
        elif "ค่าใช้จ่ายภาษีเงินได้" in line_name:
            f_cy = fs_detail_formula("D_Income_Tax", "ค่าใช้จ่ายภาษีเงินได้", "H", negate=True)
            f_py = fs_detail_formula("D_Income_Tax", "ค่าใช้จ่ายภาษีเงินได้", "J", negate=True)
        elif "กำไร (ขาดทุน) สุทธิสำหรับงวด" in line_name:
            ebt_r = is_row_map["กำไร (ขาดทุน) ก่อนค่าใช้จ่ายภาษีเงินได้"]
            tax_r = is_row_map["หัก ค่าใช้จ่ายภาษีเงินได้"]
            f_cy = f"=D{ebt_r}+D{tax_r}"
            f_py = f"=E{ebt_r}+E{tax_r}"
            net_income_row = idx_r
        elif "OCI" in line_name:
            f_cy = "=0"
            f_py = "=0"
        else:
            f_cy = f"=D{net_income_row}+D{idx_r-1}"
            f_py = f"=E{net_income_row}+E{idx_r-1}"

        vals = [r["Section"], line_name, r["Note"], f_cy, f_py, f"'{f_cy}", r["Source_Ref"]]
        is_sub_or_tot = r["Row_Type"] in ("Subtotal", "Total")
        for c_i, v in enumerate(vals, start=1):
            cell = ws_is.cell(row=idx_r, column=c_i, value=v)
            cell.border = BORDER_TOTAL if r["Row_Type"] == "Total" else BORDER_CELL
            cell.font = FONT_BOLD if is_sub_or_tot else FONT_REGULAR
            if c_i in (4, 5):
                cell.number_format = NUM_FMT
                cell.fill = FILL_TOTAL if is_sub_or_tot else FILL_CALC
        record_cell_ref("FS_Income_Statement", f"D{idx_r}", f_cy, float(r["Current_Year"]), "Detail Schedules", r["Source_Ref"], "", "", "", line_name, f"Income statement line: {line_name}")

    ws_is.cell(row=ws_is.max_row + 2, column=1, value="DRAFT FOR CPA REVIEW ONLY — งบกำไรขาดทุนฉบับร่างเพื่อการสอบทาน").font = FONT_FOOTNOTE
    _style_table_sheet(ws_is, header_row=4, freeze_cell="A5", apply_autofilter=False)
    _configure_print_setup(ws_is)
    ws_is.protection.sheet = True

    # 14. FS_Balance_Sheet (with live Excel formulas!)
    ws_bs = wb.create_sheet("FS_Balance_Sheet")
    ws_bs.cell(row=1, column=1, value=f"{setup.entity_name} — งบแสดงฐานะการเงิน (ฉบับร่าง)").font = FONT_TITLE
    ws_bs.cell(row=2, column=1, value=f"ณ วันที่ {setup.period_end} | หน่วย: {setup.currency} ({setup.unit_scale}) | แบบ: {setup.dbd_template}").font = FONT_FOOTNOTE
    bs_headers = ["หมวด", "รายการ", "หมายเหตุ", "งวดปัจจุบัน (Formula)", "งวดเปรียบเทียบ (Formula)", "สูตรอ้างอิง", "แหล่งข้อมูลต้นทาง"]
    for c_i, h in enumerate(bs_headers, start=1):
        ws_bs.cell(row=4, column=c_i, value=h)

    bs_df = fs_result.get("balance_sheet", pd.DataFrame())
    bs_line_to_detail = {
        "เงินสดและรายการเทียบเท่าเงินสด": "D_Cash_Bank",
        "ลูกหนี้การค้าและลูกหนี้อื่น": "D_AR_Trade_Other",
        "สินค้าคงเหลือ": "D_Inventory",
        "สินทรัพย์หมุนเวียนอื่น": "D_Other_Current_Assets",
        "เงินลงทุนในบริษัทย่อย บริษัทร่วม และเงินลงทุนระยะยาว": "D_Investments",
        "ที่ดิน อาคารและอุปกรณ์": "D_PPE",
        "สินทรัพย์ไม่มีตัวตน": "D_Intangible_Assets",
        "เงินเบิกเกินบัญชีและเงินกู้ยืมระยะสั้น": "D_Borrowings",
        "เจ้าหนี้การค้าและเจ้าหนี้อื่น": "D_AP_Trade_Other",
        "ค่าใช้จ่ายค้างจ่าย": "D_Accrued_Expenses",
        "ภาษีเงินได้ค้างจ่ายและภาษีอื่น": "D_Tax_Payable",
        "เงินกู้ยืมระยะยาว": "D_Borrowings",
        "หนี้สินตามสัญญาเช่า": "D_Lease_Liabilities",
        "ประมาณการหนี้สินไม่หมุนเวียนสำหรับผลประโยชน์พนักงาน": "D_Employee_Benefits",
        "ประมาณการหนี้สินอื่น": "D_Provisions",
        "ทุนที่ออกและชำระแล้ว": "D_Share_Capital",
    }
    bs_row_map: dict[str, int] = {}
    bs_cash_row = 5
    bs_tot_assets_row = 5
    bs_tot_le_row = 5

    for idx_r, (_, r) in enumerate(bs_df.iterrows(), start=5):
        line_name = str(r["Line_Item"])
        bs_row_map[line_name] = idx_r
        if line_name == "เงินสดและรายการเทียบเท่าเงินสด":
            bs_cash_row = idx_r
        if line_name in bs_line_to_detail:
            ds = bs_line_to_detail[line_name]
            f_cy = fs_detail_formula(ds, line_name, "H")
            f_py = fs_detail_formula(ds, line_name, "J")
        elif "กำไรสะสม" in line_name:
            re_det = fs_detail_formula("D_Retained_Earnings", "กำไรสะสม", "H")[1:]
            re_py = fs_detail_formula("D_Retained_Earnings", "กำไรสะสม", "J")[1:]
            f_cy = f"={re_det}+FS_Income_Statement!D{net_income_row}"
            f_py = f"={re_py}+FS_Income_Statement!E{net_income_row}"
        elif line_name == "รวมสินทรัพย์หมุนเวียน":
            f_cy = f"=SUM(D5:D{idx_r-1})"
            f_py = f"=SUM(E5:E{idx_r-1})"
        elif line_name == "รวมสินทรัพย์ไม่หมุนเวียน":
            ca_r = bs_row_map["รวมสินทรัพย์หมุนเวียน"]
            f_cy = f"=SUM(D{ca_r+1}:D{idx_r-1})"
            f_py = f"=SUM(E{ca_r+1}:E{idx_r-1})"
        elif line_name == "รวมสินทรัพย์":
            ca_r = bs_row_map["รวมสินทรัพย์หมุนเวียน"]
            nca_r = bs_row_map["รวมสินทรัพย์ไม่หมุนเวียน"]
            f_cy = f"=D{ca_r}+D{nca_r}"
            f_py = f"=E{ca_r}+E{nca_r}"
            bs_tot_assets_row = idx_r
        elif line_name == "รวมหนี้สินหมุนเวียน":
            ta_r = bs_row_map["รวมสินทรัพย์"]
            f_cy = f"=SUM(D{ta_r+1}:D{idx_r-1})"
            f_py = f"=SUM(E{ta_r+1}:E{idx_r-1})"
        elif line_name == "รวมหนี้สินไม่หมุนเวียน":
            cl_r = bs_row_map["รวมหนี้สินหมุนเวียน"]
            f_cy = f"=SUM(D{cl_r+1}:D{idx_r-1})"
            f_py = f"=SUM(E{cl_r+1}:E{idx_r-1})"
        elif line_name == "รวมหนี้สิน":
            cl_r = bs_row_map["รวมหนี้สินหมุนเวียน"]
            ncl_r = bs_row_map["รวมหนี้สินไม่หมุนเวียน"]
            f_cy = f"=D{cl_r}+D{ncl_r}"
            f_py = f"=E{cl_r}+E{ncl_r}"
        elif line_name == "รวมส่วนของเจ้าของ":
            tl_r = bs_row_map["รวมหนี้สิน"]
            f_cy = f"=SUM(D{tl_r+1}:D{idx_r-1})"
            f_py = f"=SUM(E{tl_r+1}:E{idx_r-1})"
        elif line_name == "รวมหนี้สินและส่วนของเจ้าของ":
            tl_r = bs_row_map["รวมหนี้สิน"]
            te_r = bs_row_map["รวมส่วนของเจ้าของ"]
            f_cy = f"=D{tl_r}+D{te_r}"
            f_py = f"=E{tl_r}+E{te_r}"
            bs_tot_le_row = idx_r
        else:
            f_cy = "=0"
            f_py = "=0"

        vals = [r["Section"], line_name, r["Note"], f_cy, f_py, f"'{f_cy}", r["Source_Ref"]]
        is_sub_or_tot = r["Row_Type"] in ("Subtotal", "Total")
        for c_i, v in enumerate(vals, start=1):
            cell = ws_bs.cell(row=idx_r, column=c_i, value=v)
            cell.border = BORDER_TOTAL if r["Row_Type"] == "Total" else BORDER_CELL
            cell.font = FONT_BOLD if is_sub_or_tot else FONT_REGULAR
            if c_i in (4, 5):
                cell.number_format = NUM_FMT
                cell.fill = FILL_TOTAL if is_sub_or_tot else FILL_CALC
        record_cell_ref("FS_Balance_Sheet", f"D{idx_r}", f_cy, float(r["Current_Year"]), "Detail Schedules", r["Source_Ref"], "", "", "", line_name, f"Balance sheet line: {line_name}")

    # Accounting equation check row
    chk_r = ws_bs.max_row + 1
    ws_bs.cell(row=chk_r, column=2, value="ตรวจสอบสมการบัญชี (Assets - (Liabilities + Equity))").font = FONT_BOLD
    c_chk = ws_bs.cell(row=chk_r, column=4, value=f"=D{bs_tot_assets_row}-D{bs_tot_le_row}")
    c_chk.font = FONT_BOLD
    c_chk.number_format = NUM_FMT
    c_chk.fill = FILL_PASS if abs(float(fs_result["reconciliations"].get("bs_balance_diff", 0.0))) < 0.01 else FILL_ERR
    ws_bs.cell(row=chk_r + 2, column=1, value="DRAFT FOR CPA REVIEW ONLY — งบแสดงฐานะการเงินฉบับร่างเพื่อการสอบทาน").font = FONT_FOOTNOTE
    _style_table_sheet(ws_bs, header_row=4, freeze_cell="A5", apply_autofilter=False)
    _configure_print_setup(ws_bs)
    ws_bs.protection.sheet = True

    # 15. FS_Changes_Equity (Formula linked to D_Share_Capital, D_Retained_Earnings, FS_Income_Statement!)
    ws_sce = wb.create_sheet("FS_Changes_Equity")
    ws_sce.cell(row=1, column=1, value=f"{setup.entity_name} — งบแสดงการเปลี่ยนแปลงส่วนของผู้ถือหุ้น (ฉบับร่าง)").font = FONT_TITLE
    sce_headers = ["รายการ", "ทุนที่ออกและชำระแล้ว", "กำไรสะสม", "รวมส่วนของเจ้าของ", "สูตรอ้างอิง"]
    for c_i, h in enumerate(sce_headers, start=1):
        ws_sce.cell(row=4, column=c_i, value=h)
    sc_tot = detail_totals_map["D_Share_Capital"]["total_row"]
    re_tot = detail_totals_map["D_Retained_Earnings"]["total_row"]
    sce_rows_formulas = [
        ("ยอดคงเหลือต้นงวด (ตามงบทดลองก่อนปิดกำไร)", f"=D_Share_Capital!H{sc_tot}", f"=D_Retained_Earnings!H{re_tot}", "=B5+C5", "Linked to Detail Schedules"),
        ("กำไร (ขาดทุน) สุทธิสำหรับงวด", "=0", f"=FS_Income_Statement!D{net_income_row}", "=B6+C6", "Linked to FS_Income_Statement"),
        ("ยอดคงเหลือปลายงวด", "=SUM(B5:B6)", "=SUM(C5:C6)", "=SUM(D5:D6)", "Sum of Equity Movements"),
    ]
    for offset, (lbl, fb, fc, fd, fdesc) in enumerate(sce_rows_formulas):
        r_i = 5 + offset
        for c_i, v in enumerate([lbl, fb, fc, fd, fdesc], start=1):
            c = ws_sce.cell(row=r_i, column=c_i, value=v)
            c.border = BORDER_TOTAL if offset == 2 else BORDER_CELL
            c.font = FONT_BOLD if offset == 2 else FONT_REGULAR
            if c_i in (2, 3, 4):
                c.number_format = NUM_FMT
                c.fill = FILL_TOTAL if offset == 2 else FILL_CALC
    _style_table_sheet(ws_sce, header_row=4, freeze_cell="A5", apply_autofilter=False)
    _configure_print_setup(ws_sce)
    ws_sce.protection.sheet = True

    # 16. FS_Cash_Flow
    ws_cf = wb.create_sheet("FS_Cash_Flow")
    ws_cf.cell(row=1, column=1, value=f"{setup.entity_name} — งบกระแสเงินสด (ฉบับร่าง)").font = FONT_TITLE
    note_cf = cf_result.get("message") or f"วิธี: {setup.cashflow_method}"
    ws_cf.cell(row=2, column=1, value=note_cf).font = FONT_FOOTNOTE
    cf_df = cf_result.get("cashflow_df", pd.DataFrame())
    if cf_df.empty:
        ws_cf.cell(row=4, column=1, value="สถานะ")
        ws_cf.cell(row=4, column=2, value="รายละเอียด")
        ws_cf.cell(row=5, column=1, value="N/A - Insufficient Source Data")
        ws_cf.cell(row=5, column=2, value=cf_result.get("message", "ต้องใช้ข้อมูลธนาคาร/รายละเอียดรายการเงินสดเพิ่มเติม"))
        _style_table_sheet(ws_cf, header_row=4, freeze_cell="A5", apply_autofilter=False)
    else:
        cf_headers = ["หมวดกระแสเงินสด", "รายการ", "จำนวนเงิน", "สูตรอ้างอิง", "สถานะ"]
        for c_i, h in enumerate(cf_headers, start=1):
            ws_cf.cell(row=4, column=c_i, value=h)
        for idx_r, (_, r) in enumerate(cf_df.iterrows(), start=5):
            vals = [r["Category"], r["Line_Item"], float(r["Amount"]), r["Formula_Preview"], r["Status"]]
            for c_i, v in enumerate(vals, start=1):
                c = ws_cf.cell(row=idx_r, column=c_i, value=v)
                c.border = BORDER_CELL
                c.font = FONT_BOLD if r["Status"] in ("Subtotal", "Reconciled", "Variance Detected") else FONT_REGULAR
                if c_i == 3:
                    c.number_format = NUM_FMT
        # Add reconciliation check cell linking BS Cash row!
        chk_cf_r = ws_cf.max_row + 1
        ws_cf.cell(row=chk_cf_r, column=2, value="เทียบเงินสดปลายงวดในงบแสดงฐานะการเงิน (BS Link)").font = FONT_BOLD
        c_bs_cash = ws_cf.cell(row=chk_cf_r, column=3, value=f"=FS_Balance_Sheet!D{bs_cash_row}")
        c_bs_cash.number_format = NUM_FMT
        c_bs_cash.fill = FILL_CALC
        c_diff_cf = ws_cf.cell(row=chk_cf_r + 1, column=3, value=f"=C{chk_cf_r-1}-C{chk_cf_r}")
        c_diff_cf.number_format = NUM_FMT
        ws_cf.cell(row=chk_cf_r + 1, column=2, value="ผลต่างเงินสดปลายงวด (CF - BS)").font = FONT_BOLD
        _style_table_sheet(ws_cf, header_row=4, freeze_cell="A5", apply_autofilter=False)
    _configure_print_setup(ws_cf)
    ws_cf.protection.sheet = True

    # 17. Notes, Reviews, Risk, Workpaper, Supplementary Audit Sheets, Auditor Report
    _write_df_to_sheet(wb, "Notes_Index", notes_index_df, numeric_cols={"Account_Count", "TB_Amount"}, status_col="Status")
    _write_df_to_sheet(wb, "Notes_Draft", notes_draft_df, status_col="Status")
    _write_df_to_sheet(wb, "Revenue_Review", rev_review_df, numeric_cols={"Amount", "Risk_Score"}, status_col="Risk_Level")
    _write_df_to_sheet(wb, "Expense_Review", exp_review_df, numeric_cols={"Amount", "Risk_Score"}, status_col="Risk_Level")
    _write_df_to_sheet(wb, "Audit_Risk_Register", risk_reg_df, numeric_cols={"Population_Amount", "Materiality_Ratio", "Risk_Score"}, status_col="Risk_Level")
    _write_df_to_sheet(wb, "Audit_Workpaper", workpaper_df, numeric_cols={"Population_Amount", "Sample_Size_Suggestion"}, status_col="Risk_Rating")
    _write_df_to_sheet(wb, "Confirmation_Request_List", supp_audit.get("Confirmation_Request_List", pd.DataFrame()), numeric_cols={"Book_Balance", "Confirmed_Balance", "Difference"})
    _write_df_to_sheet(wb, "Subsequent_Events", supp_audit.get("Subsequent_Events", pd.DataFrame()), numeric_cols={"Amount"})
    _write_df_to_sheet(wb, "Related_Party_Check", supp_audit.get("Related_Party_Check", pd.DataFrame()), numeric_cols={"Adjusted_Amount"})
    _write_df_to_sheet(wb, "Tax_Check", supp_audit.get("Tax_Check", pd.DataFrame()), numeric_cols={"Book_Balance"})
    _write_df_to_sheet(wb, "Auditor_Report_Draft", auditor_draft_df, status_col="Approval_Status")
    _write_df_to_sheet(wb, "Auditor_Report_Ref", auditor_ref_df)

    # 18. Management_Dashboard_Data (Formula-driven KPIs!)
    ws_kpi = wb.create_sheet("Management_Dashboard_Data")
    ws_kpi.cell(row=1, column=1, value="KPI").font = FONT_HEADER
    ws_kpi.cell(row=1, column=2, value="Value (Formula)").font = FONT_HEADER
    ws_kpi.cell(row=1, column=3, value="Formula_Text").font = FONT_HEADER
    ws_kpi.cell(row=1, column=4, value="Source_Ref").font = FONT_HEADER

    r_rev = is_row_map.get("รายได้จากการขายหรือการให้บริการ", 5)
    r_gp = is_row_map.get("กำไร (ขาดทุน) ขั้นต้น", 7)
    r_ni = net_income_row
    r_ca = bs_row_map.get("รวมสินทรัพย์หมุนเวียน", 9)
    r_cl = bs_row_map.get("รวมหนี้สินหมุนเวียน", 18)
    r_tl = bs_row_map.get("รวมหนี้สิน", 24)
    r_te = bs_row_map.get("รวมส่วนของเจ้าของ", 27)
    kpi_defs = [
        ("รายได้รวม", f"=FS_Income_Statement!D{r_rev}", "FS_Income_Statement"),
        ("กำไรขั้นต้น", f"=FS_Income_Statement!D{r_gp}", "FS_Income_Statement"),
        ("กำไรสุทธิ", f"=FS_Income_Statement!D{r_ni}", "FS_Income_Statement"),
        ("อัตรากำไรขั้นต้น (%)", f"=IF(B2=0,0,B3/B2)", "Calculated KPI"),
        ("อัตรากำไรสุทธิ (%)", f"=IF(B2=0,0,B4/B2)", "Calculated KPI"),
        ("เงินสดและรายการเทียบเท่าเงินสด", f"=FS_Balance_Sheet!D{bs_cash_row}", "FS_Balance_Sheet"),
        ("อัตราส่วนสภาพคล่อง (Current Ratio)", f"=IF(FS_Balance_Sheet!D{r_cl}=0,0,FS_Balance_Sheet!D{r_ca}/FS_Balance_Sheet!D{r_cl})", "FS_Balance_Sheet"),
        ("อัตราส่วนหนี้สินต่อทุน (D/E Ratio)", f"=IF(FS_Balance_Sheet!D{r_te}=0,0,FS_Balance_Sheet!D{r_tl}/FS_Balance_Sheet!D{r_te})", "FS_Balance_Sheet"),
        ("จำนวนบัญชี Unmapped", f"=COUNTA(Unmapped_Accounts!A2:A{max(2, len(unmapped_df)+1)})", "Unmapped_Accounts"),
    ]
    for idx_k, (k_name, k_f, k_src) in enumerate(kpi_defs, start=2):
        ws_kpi.cell(row=idx_k, column=1, value=k_name).font = FONT_BOLD
        c_val = ws_kpi.cell(row=idx_k, column=2, value=k_f)
        c_val.fill = FILL_CALC
        c_val.number_format = "0.00%" if "(%)" in k_name else NUM_FMT
        ws_kpi.cell(row=idx_k, column=3, value=f"'{k_f}")
        ws_kpi.cell(row=idx_k, column=4, value=k_src)
    _style_table_sheet(ws_kpi, header_row=1, freeze_cell="A2", apply_autofilter=False)

    # 19. Cell_Formula_Map, Source_Traceability, Change_Log
    _write_df_to_sheet(wb, "Cell_Formula_Map", pd.DataFrame(cell_formula_map), numeric_cols={"DisplayedValue"})
    _write_df_to_sheet(wb, "Source_Traceability", pd.DataFrame(source_trace_rows))
    _write_df_to_sheet(wb, "Change_Log", pd.DataFrame(change_log) if change_log else pd.DataFrame([{"Timestamp": datetime.now().isoformat(timespec="seconds"), "Module": "Export", "Action": "Generate Workbook", "Note": filename}]))

    # Pass 1: Save bytes & verify formulas
    buf1 = io.BytesIO()
    wb.save(buf1)
    formula_check_df = verify_workbook_formulas(buf1.getvalue())

    # Inject Formula_Check sheet and save Pass 2
    _write_df_to_sheet(wb, "Formula_Check", formula_check_df, numeric_cols={"Formula_Cells_Count", "Missing_Sheet_Refs", "Error_Token_Count"}, status_col="Status")
    wb["Formula_Check"].protection.sheet = True
    buf2 = io.BytesIO()
    wb.save(buf2)
    final_bytes = buf2.getvalue()

    # Final verification pass confirming Formula_Check itself didn't break anything
    final_check_df = verify_workbook_formulas(final_bytes)
    return final_bytes, filename, final_check_df
