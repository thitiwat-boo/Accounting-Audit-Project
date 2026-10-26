from __future__ import annotations
import pandas as pd
from .validators import duplicate_gl_rows

def create_risk_register(gl: pd.DataFrame, period_end=None, materiality=100000):
    cols=['Risk ID','Account','Amount','Assertion','Risk Reason','Rule Triggered','Suggested Procedure','Evidence Needed','Source Ref','Risk Rating','Owner','Status','Conclusion']
    if gl.empty: return pd.DataFrame(columns=cols)
    rows=[]; end=pd.to_datetime(period_end) if period_end else None
    dates=pd.to_datetime(gl['Date'],errors='coerce',dayfirst=True) if 'Date' in gl else pd.Series([pd.NaT]*len(gl),index=gl.index)
    for idx,r in gl.iterrows():
        debit=pd.to_numeric(pd.Series([r.get('Debit',0)]),errors='coerce').fillna(0).iloc[0]; credit=pd.to_numeric(pd.Series([r.get('Credit',0)]),errors='coerce').fillna(0).iloc[0]; amount=max(abs(float(debit)),abs(float(credit)))
        triggers=[]; assertion='Accuracy / Cut-off'; score=0
        desc=str(r.get('Description','')).lower(); name=str(r.get('Account Name','')).lower(); doc=str(r.get('Document No','')).lower()
        if amount>=materiality: triggers.append('Large transaction / materiality threshold'); score+=25
        if end is not None and pd.notna(dates.loc[idx]) and 0 <= (end-dates.loc[idx]).days <= 3: triggers.append('รายการใกล้วันสิ้นงวด'); score+=25; assertion='Cut-off'
        if any(x in desc for x in ['manual','ปรับปรุง','adjustment','journal','ปิดบัญชี']): triggers.append('Manual journal indicator'); score+=20
        if not str(r.get('Document No','')).strip(): triggers.append('ไม่มีเลขที่เอกสาร'); score+=15
        if any(x in name+' '+desc for x in ['กรรมการ','ผู้ถือหุ้น','related party','ระหว่างกัน']): triggers.append('Related-party indicator'); score+=25
        if any(x in name for x in ['พักบัญชี','suspense','บัญชีพัก']): triggers.append('Suspense account'); score+=30
        if triggers:
            rows.append({'Risk ID':f'R{len(rows)+1:04d}','Account':r.get('Account Name',r.get('Account Code','')),'Amount':amount,'Assertion':assertion,
                         'Risk Reason':'Risk indicator only; ไม่ใช่ข้อสรุปว่ามีทุจริต','Rule Triggered':'; '.join(triggers),'Suggested Procedure':'ตรวจเอกสารต้นทาง การอนุมัติ คู่รายการ และงวดบัญชีที่เกี่ยวข้อง',
                         'Evidence Needed':'ใบสำคัญ เอกสารภาษี/สัญญา หลักฐานอนุมัติ และรายการธนาคารตามความเหมาะสม','Source Ref':f"GL row {r.get('_Source_Row',idx+2)} | Doc {r.get('Document No','')}",
                         'Risk Rating':'High' if score>=50 else 'Medium' if score>=25 else 'Low','Owner':'','Status':'Open','Conclusion':'Pending review'})
    dups=duplicate_gl_rows(gl)
    for _,r in dups.iterrows():
        rows.append({'Risk ID':f'R{len(rows)+1:04d}','Account':r.get('Account Name',r.get('Account Code','')),'Amount':max(abs(float(r.get('Debit',0) or 0)),abs(float(r.get('Credit',0) or 0))),
                     'Assertion':'Occurrence / Accuracy','Risk Reason':'รายการเหมือนกันตาม composite key ต้องยืนยันก่อนสรุป','Rule Triggered':'Duplicate composite key','Suggested Procedure':'เปรียบเทียบเอกสารต้นทางและตรวจว่าบันทึกซ้ำจริงหรือไม่',
                     'Evidence Needed':'ใบสำคัญและเอกสารต้นทาง','Source Ref':f"GL row {r.get('_Source_Row','')} | Doc {r.get('Document No','')}",'Risk Rating':'Medium','Owner':'','Status':'Open','Conclusion':'Pending review'})
    return pd.DataFrame(rows,columns=cols)
