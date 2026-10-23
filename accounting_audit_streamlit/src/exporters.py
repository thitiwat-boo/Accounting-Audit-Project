from __future__ import annotations
from io import BytesIO
import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

def export_workbook(tables: dict[str,pd.DataFrame], parameters: dict) -> bytes:
    bio=BytesIO()
    with pd.ExcelWriter(bio,engine="openpyxl") as writer:
        pd.DataFrame([{"Parameter":k,"Value":v} for k,v in parameters.items()]).to_excel(writer,sheet_name="Parameters",index=False)
        pd.DataFrame([{"Notice":"DRAFT - ต้องสอบทานโดยฝ่ายบัญชี ฝ่ายบริหาร และ CPA ตามความเหมาะสม"},
                      {"Notice":"ตัวเลขในงบเป็นข้อเสนอจากข้อมูลและ Mapping ที่ยืนยันแล้วเท่านั้น"}]).to_excel(writer,sheet_name="README",index=False)
        for name,df in tables.items():
            if df is not None and isinstance(df,pd.DataFrame):
                safe=name[:31]
                (df if not df.empty else pd.DataFrame({"Status":["No data / Insufficient source data"]})).to_excel(writer,sheet_name=safe,index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes="A2"
            ws.auto_filter.ref=ws.dimensions
            for cell in ws[1]:
                cell.font=Font(bold=True,color="FFFFFF")
                cell.fill=PatternFill("solid",fgColor="1F5A94")
            for col in ws.columns:
                letter=get_column_letter(col[0].column)
                maxlen=min(max([len(str(c.value or "")) for c in col[:200]]+[10]),42)
                ws.column_dimensions[letter].width=maxlen+2
    return bio.getvalue()
