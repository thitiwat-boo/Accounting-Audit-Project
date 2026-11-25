from __future__ import annotations

import io
import re
from typing import Any
import fitz  # PyMuPDF
import openpyxl
import pandas as pd
from PIL import Image
import pytesseract


def _extract_amounts_from_line(line: str) -> list[float]:
    matches = re.findall(r"\(?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?", line)
    vals: list[float] = []
    for m in matches:
        raw = m.strip()
        if not raw or raw in ("-", "."):
            continue
        is_neg = raw.startswith("(") and raw.endswith(")")
        num_str = raw.replace("(", "").replace(")", "").replace(",", "")
        try:
            v = float(num_str)
            if is_neg:
                v = -v
            vals.append(v)
        except ValueError:
            continue
    return vals


def extract_prior_year_excel(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Extract comparative figures from Prior Year Excel (.xlsx) preserving sheet & row Ref."""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    rows: list[dict[str, Any]] = []
    header_text: list[str] = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for r_idx, row_vals in enumerate(ws.iter_rows(values_only=True), start=1):
            non_empty = [v for v in row_vals if v is not None and str(v).strip() != ""]
            if not non_empty:
                continue
            if r_idx <= 5:
                header_text.extend([str(v).strip() for v in non_empty])

            # Identify label (first string cell) and numeric amount(s)
            label = ""
            nums: list[float] = []
            for v in row_vals:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    nums.append(float(v))
                elif isinstance(v, str):
                    s = v.strip()
                    if not label and s and not re.fullmatch(r"[\d,\.\-\(\)]+", s):
                        label = s
                    else:
                        parsed = _extract_amounts_from_line(s)
                        if parsed and re.fullmatch(r"[\d,\.\-\(\)\s]+", s):
                            nums.extend(parsed)
            if label and nums:
                rows.append(
                    {
                        "PriorYearFile": filename,
                        "PriorYearSheetOrPage": sheet_name,
                        "PriorYearSourceRowOrBoundingBox": f"Row {r_idx}",
                        "ExtractedLabel": label,
                        "ExtractedAmount": float(nums[-1]),
                        "ExtractionMethod": "Excel Direct Read",
                        "Confidence": 0.95,
                        "UserConfirmed": False,
                        "ReclassificationNote": "",
                        "Mapped_FS_Line_Item": "",
                    }
                )
    wb.close()
    meta = {
        "file_type": "Excel",
        "header_preview": " | ".join(header_text[:10]),
        "ocr_used": False,
    }
    return pd.DataFrame(rows), meta


def extract_prior_year_pdf(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Extract text/OCR from Prior Year PDF with page & bounding-box Ref. Never marks OCR as final."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    rows: list[dict[str, Any]] = []
    ocr_used = False
    ocr_warning = ""
    header_preview: list[str] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
        text_blocks = [b for b in blocks if str(b[4]).strip()]

        if text_blocks:
            for b in text_blocks:
                x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], str(b[4])
                bbox_str = f"bbox({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})"
                for line in txt.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if page_num == 1 and len(header_preview) < 8:
                        header_preview.append(line)
                    nums = _extract_amounts_from_line(line)
                    if nums:
                        # Clean label before first large number
                        label_part = re.sub(r"\(?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?", "", line).strip(" .:-")
                        if label_part and len(label_part) >= 2:
                            rows.append(
                                {
                                    "PriorYearFile": filename,
                                    "PriorYearSheetOrPage": f"Page {page_num}",
                                    "PriorYearSourceRowOrBoundingBox": bbox_str,
                                    "ExtractedLabel": label_part,
                                    "ExtractedAmount": float(nums[-1]),
                                    "ExtractionMethod": "Text PDF (PyMuPDF)",
                                    "Confidence": 0.85,
                                    "UserConfirmed": False,
                                    "ReclassificationNote": "Needs Review",
                                    "Mapped_FS_Line_Item": "",
                                }
                            )
        else:
            # Scanned PDF fallback using OCR
            ocr_used = True
            try:
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                try:
                    ocr_text = pytesseract.image_to_string(img, lang="tha+eng")
                except Exception:
                    ocr_text = pytesseract.image_to_string(img, lang="eng")

                for l_idx, line in enumerate(ocr_text.splitlines(), start=1):
                    line = line.strip()
                    if not line:
                        continue
                    if page_num == 1 and len(header_preview) < 8:
                        header_preview.append(line)
                    nums = _extract_amounts_from_line(line)
                    if nums:
                        label_part = re.sub(r"\(?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?", "", line).strip(" .:-")
                        if label_part and len(label_part) >= 2:
                            rows.append(
                                {
                                    "PriorYearFile": filename,
                                    "PriorYearSheetOrPage": f"Page {page_num}",
                                    "PriorYearSourceRowOrBoundingBox": f"OCR Line {l_idx}",
                                    "ExtractedLabel": label_part,
                                    "ExtractedAmount": float(nums[-1]),
                                    "ExtractionMethod": "OCR (Tesseract - Needs Review)",
                                    "Confidence": 0.60,
                                    "UserConfirmed": False,
                                    "ReclassificationNote": "Needs Review - OCR Mandatory Verification",
                                    "Mapped_FS_Line_Item": "",
                                }
                            )
            except Exception as exc:
                ocr_warning = f"OCR ไม่สามารถประมวลผลหน้า {page_num} ได้ ({exc}) — กรุณาอัปโหลดไฟล์ Excel หรือกรอกยอดเปรียบเทียบด้วยตนเอง"

    doc.close()
    meta = {
        "file_type": "PDF (OCR)" if ocr_used else "PDF (Text)",
        "header_preview": " | ".join(header_preview[:8]),
        "ocr_used": ocr_used,
        "ocr_warning": ocr_warning,
    }
    return pd.DataFrame(rows), meta


def verify_prior_year_entity_match(header_preview: str, entity_name: str, reg_no: str, comp_label: str) -> dict[str, Any]:
    """Check whether Prior Year file header matches current entity name / reg no / comparative period."""
    text = header_preview or ""
    core_name = entity_name.replace("บริษัท", "").replace("จำกัด", "").replace("(มหาชน)", "").strip()
    name_match = bool(core_name and core_name in text)
    reg_match = bool(reg_no.strip() and reg_no.strip() in text)
    period_match = bool(comp_label.strip() and comp_label.strip() in text)
    return {
        "entity_name_matched": name_match,
        "reg_no_matched": reg_match,
        "comparative_period_matched": period_match,
        "status": "Match" if (name_match or reg_match) and period_match else "Needs Verification",
    }


def reconcile_prior_year_with_opening_tb(
    prior_df: pd.DataFrame,
    tb_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compare extracted Prior Year FS line items against TB Opening/Prior balances."""
    if prior_df.empty:
        return pd.DataFrame()

    # Aggregate TB opening/prior balance by FS_Line_Item if mapping exists
    tb_grouped: dict[str, float] = {}
    if not tb_df.empty and not mapping_df.empty:
        merged = tb_df.merge(
            mapping_df[["Account_Code", "FS_Line_Item", "FS_Sign"]],
            on="Account_Code",
            how="left",
        )
        merged["FS_Sign"] = pd.to_numeric(merged["FS_Sign"], errors="coerce").fillna(1.0)
        base_col = "Prior_Balance" if merged["Prior_Balance"].abs().sum() > 0 else "Opening_Balance"
        merged["Signed_Prior"] = merged[base_col] * merged["FS_Sign"]
        grp = merged.groupby("FS_Line_Item", dropna=True)["Signed_Prior"].sum()
        tb_grouped = grp.to_dict()

    rows = []
    for _, r in prior_df.iterrows():
        target = str(r.get("Mapped_FS_Line_Item") or r.get("ExtractedLabel") or "").strip()
        py_amt = float(r.get("ExtractedAmount", 0.0) or 0.0)
        tb_amt = float(tb_grouped.get(target, 0.0))
        diff = round(py_amt - tb_amt, 2)
        rows.append(
            {
                "PriorYearFile": r.get("PriorYearFile", ""),
                "Ref_Page_Row": f"{r.get('PriorYearSheetOrPage', '')} / {r.get('PriorYearSourceRowOrBoundingBox', '')}",
                "ExtractedLabel": r.get("ExtractedLabel", ""),
                "Mapped_FS_Line_Item": target,
                "ExtractedAmount": py_amt,
                "TB_Opening_or_Prior": tb_amt,
                "Difference": diff,
                "ExtractionMethod": r.get("ExtractionMethod", ""),
                "Confidence": r.get("Confidence", 0.0),
                "UserConfirmed": bool(r.get("UserConfirmed", False)),
                "Status": "Matched" if abs(diff) < 1.0 and r.get("UserConfirmed") else "Needs Review",
                "ReclassificationNote": r.get("ReclassificationNote", ""),
            }
        )
    return pd.DataFrame(rows)
