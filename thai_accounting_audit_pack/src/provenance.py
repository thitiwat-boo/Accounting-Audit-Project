from __future__ import annotations

import io
import re
from typing import Any
import openpyxl
import pandas as pd


EXCEL_ERROR_TOKENS = ("#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#N/A", "#NUM!")


def verify_workbook_formulas(workbook_bytes: bytes, expected_values: dict[tuple[str, str], float] | None = None) -> pd.DataFrame:
    """Inspect generated .xlsx WITHOUT data_only=True to verify formulas exist, refs are valid, and no Excel errors appear."""
    wb = openpyxl.load_workbook(io.BytesIO(workbook_bytes), data_only=False)
    sheet_set = set(wb.sheetnames)
    expected = expected_values or {}
    results: list[dict[str, Any]] = []

    sheet_ref_pattern = re.compile(r"(?:'([^']+)'|([A-Za-z0-9_]+))!")

    for sname in wb.sheetnames:
        if not (sname.startswith("FS_") or sname.startswith("D_") or sname in ("Adjusted_TB", "TB_Normalized")):
            continue
        ws = wb[sname]
        formula_count = 0
        error_cells: list[str] = []
        missing_sheet_refs: list[str] = []

        for row in ws.iter_rows(values_only=False):
            for cell in row:
                val = cell.value
                if isinstance(val, str):
                    if any(tok in val for tok in EXCEL_ERROR_TOKENS):
                        error_cells.append(f"{cell.coordinate}:{val}")
                    if val.startswith("="):
                        formula_count += 1
                        for m in sheet_ref_pattern.finditer(val):
                            ref_sheet = m.group(1) or m.group(2)
                            if ref_sheet and ref_sheet not in sheet_set:
                                missing_sheet_refs.append(f"{cell.coordinate}->{ref_sheet}")

        status = "Pass"
        note = f"ตรวจพบสูตรจริงจำนวน {formula_count} เซลล์ และไม่พบ error tokens"
        if missing_sheet_refs or error_cells:
            status = "Error"
            note = f"Missing sheets: {missing_sheet_refs[:5]} | Error tokens: {error_cells[:5]}"
        elif sname.startswith(("FS_", "D_")) and formula_count == 0:
            # Cash flow may legitimately show N/A if insufficient data
            if sname == "FS_Cash_Flow":
                status = "Warning"
                note = "ไม่พบสูตร (อาจอยู่ในสถานะ Insufficient Data หรือไม่ได้จัดทำ)"
            else:
                status = "Warning"
                note = "ไม่พบสูตรคำนวณใน Sheet นี้ (อาจไม่มีบัญชีที่ map เข้ามา)"

        results.append(
            {
                "Sheet_Name": sname,
                "Formula_Cells_Count": formula_count,
                "Missing_Sheet_Refs": len(missing_sheet_refs),
                "Error_Token_Count": len(error_cells),
                "Status": status,
                "Details": note,
            }
        )

    # Also verify expected Python values on key mapped cells if provided
    for (sname, coord), py_val in expected.items():
        if sname in sheet_set:
            cell_val = wb[sname][coord].value
            is_formula = isinstance(cell_val, str) and cell_val.startswith("=")
            results.append(
                {
                    "Sheet_Name": f"{sname}!{coord}",
                    "Formula_Cells_Count": 1 if is_formula else 0,
                    "Missing_Sheet_Refs": 0,
                    "Error_Token_Count": 0 if is_formula else 1,
                    "Status": "Pass" if is_formula else "Error",
                    "Details": f"Formula={cell_val} | Python Expected Value={py_val:,.2f}",
                }
            )

    wb.close()
    return pd.DataFrame(results)
