from __future__ import annotations
import pandas as pd
from io import BytesIO

TB_ALIASES = {
 "Account Code":["Account Code","รหัสบัญชี","เลขที่บัญชี","รหัสบัญชีแยกประเภท","Account"],
 "Account Name":["Account Name","ชื่อบัญชี","ชื่อบัญชีแยกประเภท","รายการบัญชี"],
 "Debit":["Debit","เดบิต","ยอดเดบิต","Dr"],
 "Credit":["Credit","เครดิต","ยอดเครดิต","Cr"],
 "Balance":["Balance","ยอดคงเหลือ","คงเหลือ"]
}
GL_ALIASES = {
 "Date":["Date","วันที่","Posting Date","วันที่บันทึก"],
 "Document No":["Document No","เลขที่เอกสาร","Voucher No","เลขที่ใบสำคัญ"],
 "Account Code":["Account Code","รหัสบัญชี","เลขที่บัญชี"],
 "Account Name":["Account Name","ชื่อบัญชี"],
 "Description":["Description","รายละเอียด","คำอธิบายรายการ"],
 "Debit":["Debit","เดบิต","ยอดเดบิต","Dr"],
 "Credit":["Credit","เครดิต","ยอดเครดิต","Cr"],
 "Reference":["Reference","อ้างอิง","เลขที่อ้างอิง"]
}
def read_excel_sheets(uploaded_file):
    return pd.read_excel(uploaded_file, sheet_name=None, dtype=object)

def suggest_columns(columns, aliases):
    normalized={str(c).strip().lower():c for c in columns}
    out={}
    for target, names in aliases.items():
        match=None
        for name in names:
            if name.lower() in normalized:
                match=normalized[name.lower()]; break
        out[target]=match
    return out

def normalize_columns(df, mapping):
    result=df.copy()
    rename={source:target for target,source in mapping.items() if source and source in result.columns}
    result=result.rename(columns=rename)
    for col in ["Debit","Credit","Balance","Amount"]:
        if col in result:
            result[col]=pd.to_numeric(result[col].astype(str).str.replace(",","",regex=False),errors="coerce").fillna(0.0)
    result["_Source_Row"]=range(2,len(result)+2)
    return result
