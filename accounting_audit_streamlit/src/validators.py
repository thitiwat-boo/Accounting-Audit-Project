from __future__ import annotations
import pandas as pd

def check_columns(df: pd.DataFrame, required: list[str]) -> list[str]:
    return [c for c in required if c not in df.columns]

def tb_quality(tb: pd.DataFrame, debit_col="Debit", credit_col="Credit") -> pd.DataFrame:
    rows = []
    if debit_col not in tb or credit_col not in tb:
        return pd.DataFrame([{"Check":"TB debit/credit columns", "Status":"Error",
                              "Detail":f"ต้องมีคอลัมน์ {debit_col} และ {credit_col}"}])
    debit = pd.to_numeric(tb[debit_col], errors="coerce").fillna(0).sum()
    credit = pd.to_numeric(tb[credit_col], errors="coerce").fillna(0).sum()
    diff = round(float(debit-credit), 2)
    rows.append({"Check":"TB debit = credit","Status":"Pass" if abs(diff)<0.01 else "Error",
                 "Detail":f"Debit={debit:,.2f}; Credit={credit:,.2f}; Difference={diff:,.2f}"})
    if "Account Code" in tb:
        dup = int(tb["Account Code"].astype(str).duplicated(keep=False).sum())
        rows.append({"Check":"Duplicate account codes","Status":"Warning" if dup else "Pass",
                     "Detail":f"จำนวนแถวที่รหัสบัญชีซ้ำ: {dup}"})
    return pd.DataFrame(rows)

def gl_quality(gl: pd.DataFrame, date_col="Date", debit_col="Debit", credit_col="Credit") -> pd.DataFrame:
    rows=[]
    if date_col in gl:
        dates = pd.to_datetime(gl[date_col], errors="coerce", dayfirst=True)
        n=int(dates.isna().sum())
        rows.append({"Check":"GL date validity","Status":"Warning" if n else "Pass",
                     "Detail":f"วันที่ว่างหรืออ่านไม่ได้ {n} แถว"})
    else:
        rows.append({"Check":"GL date column","Status":"Warning","Detail":f"ไม่พบคอลัมน์ {date_col}"})
    if debit_col in gl and credit_col in gl:
        d=pd.to_numeric(gl[debit_col],errors="coerce").fillna(0)
        c=pd.to_numeric(gl[credit_col],errors="coerce").fillna(0)
        both=((d.abs()>0)&(c.abs()>0)).sum()
        rows.append({"Check":"GL debit and credit on same row","Status":"Warning" if both else "Pass",
                     "Detail":f"พบแถวที่มีเดบิตและเครดิตพร้อมกัน {int(both)} แถว"})
    if "Document No" in gl:
        n=int(gl["Document No"].astype(str).duplicated(keep=False).sum())
        rows.append({"Check":"Repeated document numbers","Status":"Warning" if n else "Pass",
                     "Detail":f"แถวที่เลขที่เอกสารซ้ำ {n} แถว (ต้องพิจารณาตามระบบงาน)"})
    return pd.DataFrame(rows)
