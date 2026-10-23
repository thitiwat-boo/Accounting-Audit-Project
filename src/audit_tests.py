from __future__ import annotations
import pandas as pd

def duplicate_gl_rows(gl: pd.DataFrame) -> pd.DataFrame:
    cols=[c for c in ["Date","Document No","Account Code","Description","Debit","Credit"] if c in gl]
    if not cols: return pd.DataFrame()
    return gl[gl.duplicated(subset=cols,keep=False)].copy()

def create_risk_register(gl: pd.DataFrame, period_end=None) -> pd.DataFrame:
    if gl.empty: return pd.DataFrame(columns=["Risk ID","Account","GL Reference","Risk Area","Assertion","Rule Triggered","Amount","Risk Score","Risk Level","Suggested Procedure","Evidence Needed","Status","Comment"])
    rows=[]
    end=pd.to_datetime(period_end) if period_end else None
    dates=pd.to_datetime(gl["Date"],errors="coerce",dayfirst=True) if "Date" in gl else pd.Series([pd.NaT]*len(gl))
    for idx,r in gl.iterrows():
        score=0; triggers=[]
        amt=abs(float(r.get("Debit",0) or 0))+abs(float(r.get("Credit",0) or 0))
        if amt>=100000: score+=20; triggers.append("ยอดรายการสูงตาม threshold เริ่มต้น")
        if end is not None and pd.notna(dates.loc[idx]) and 0 <= (end-dates.loc[idx]).days <= 3:
            score+=25; triggers.append("รายการใกล้วันสิ้นงวด")
        desc=str(r.get("Description","")).lower()
        if any(x in desc for x in ["manual","ปรับปรุง","adjustment","journal"]):
            score+=20; triggers.append("คำอธิบายอาจสื่อถึง manual journal")
        if not str(r.get("Document No","")).strip():
            score+=15; triggers.append("ไม่มีเลขที่เอกสาร")
        if score:
            rows.append({"Risk ID":f"R{len(rows)+1:04d}","Account":r.get("Account Name",r.get("Account Code","")),
             "GL Reference":f"Row {r.get('_Source_Row',idx+2)}","Risk Area":"Journal / Cut-off",
             "Assertion":"Cut-off / Accuracy","Rule Triggered":"; ".join(triggers),"Amount":amt,
             "Risk Score":min(score,100),"Risk Level":"High" if score>=50 else "Medium" if score>=25 else "Low",
             "Suggested Procedure":"Suggested Audit Procedure: ตรวจสอบเอกสารประกอบ อนุมัติ และงวดบัญชี",
             "Evidence Needed":"ใบสำคัญ รายการอนุมัติ เอกสารต้นทาง","Status":"Open","Comment":""})
    return pd.DataFrame(rows)
