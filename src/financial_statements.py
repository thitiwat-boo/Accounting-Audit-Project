from __future__ import annotations
import pandas as pd

BS_LINES=['เงินสดและรายการเทียบเท่าเงินสด','ลูกหนี้การค้าและลูกหนี้อื่น','สินค้าคงเหลือ','สินทรัพย์หมุนเวียนอื่น','ที่ดิน อาคารและอุปกรณ์','สินทรัพย์ไม่มีตัวตน','เงินลงทุน','เจ้าหนี้การค้าและเจ้าหนี้อื่น','เงินกู้ยืม','ภาษีค้างจ่าย','ประมาณการหนี้สิน','ทุน','กำไรสะสม']
IS_LINES=['รายได้จากการขายหรือการให้บริการ','รายได้อื่น','ต้นทุนขายหรือต้นทุนการให้บริการ','ค่าใช้จ่ายในการขาย','ค่าใช้จ่ายในการบริหาร','ค่าใช้จ่ายทางการเงิน','ภาษีเงินได้']

def build_statement(tb: pd.DataFrame, mapping: pd.DataFrame, adjustments: pd.DataFrame|None=None):
    if tb.empty or mapping.empty:
        return {'balance_sheet':pd.DataFrame(),'income_statement':pd.DataFrame(),'unmapped_or_pending':pd.DataFrame(),'warnings':['ต้องนำเข้า TB และ Mapping ก่อน'],'blocked':True}
    data=tb.copy(); mp=mapping.copy()
    data['Account Code']=data['Account Code'].fillna('').astype(str).str.strip(); mp['Account Code']=mp['Account Code'].fillna('').astype(str).str.strip()
    # Prevent one account from being multiplied by duplicate mapping rows.
    mp=mp.drop_duplicates('Account Code',keep='last')
    data=data.merge(mp[['Account Code','Grouping','Sub Grouping','Financial Statement','Financial Statement Line Item','Account Type','Reviewer Status']],on='Account Code',how='left',suffixes=('','_map'),validate='many_to_one')
    for col in ['Debit','Credit']:
        data[col]=pd.to_numeric(data[col],errors='coerce')
    data['Net Debit']=data.Debit.fillna(0)-data.Credit.fillna(0)
    data['Presentation Amount']=data['Net Debit']
    data.loc[data['Account Type'].isin(['Liability','Equity','Revenue']),'Presentation Amount'] *= -1
    approved=data[data['Reviewer Status'].eq('Approved')].copy()
    unresolved=data[~data['Reviewer Status'].eq('Approved')].copy()
    bs=approved[approved['Account Type'].isin(['Asset','Liability','Equity'])].groupby(['Grouping','Sub Grouping','Financial Statement Line Item'],dropna=False)['Presentation Amount'].sum().reset_index().rename(columns={'Presentation Amount':'Draft Amount'})
    inc=approved[approved['Account Type'].isin(['Revenue','Expense'])].groupby(['Grouping','Sub Grouping','Financial Statement Line Item'],dropna=False)['Presentation Amount'].sum().reset_index().rename(columns={'Presentation Amount':'Draft Amount'})
    d=float(data.Debit.fillna(0).sum()); c=float(data.Credit.fillna(0).sum())
    warnings=[]
    if abs(d-c)>=.01: warnings.append(f'TB ไม่สมดุล: debit-credit={d-c:,.2f}')
    if len(unresolved): warnings.append(f'BLOCKED: มี {len(unresolved)} บัญชีที่ยังไม่ Approved')
    if abs(d-c)>=.01: warnings.append('BLOCKED: TB debit ไม่เท่ากับ credit')
    if data['Account Type'].eq('Unclassified').any(): warnings.append('BLOCKED: มีบัญชี Unclassified แม้ถูกตั้งสถานะ Approved')
    # Profit can only be calculated from approved revenue/expense mappings.
    net_income=float(inc['Draft Amount'].sum()) if not inc.empty else None
    return {'balance_sheet':bs,'income_statement':inc,'unmapped_or_pending':unresolved,'warnings':warnings,'blocked':bool(len(unresolved) or abs(d-c)>=.01 or data['Account Type'].eq('Unclassified').any()),
            'normalized_tb':data,'net_income':net_income,'tb_debit':d,'tb_credit':c}

def draft_notes_checklist():
    topics=['ข้อมูลทั่วไปของกิจการ','เกณฑ์การจัดทำงบการเงิน','นโยบายการบัญชีที่สำคัญ','เงินสดและรายการเทียบเท่าเงินสด','ลูกหนี้การค้าและลูกหนี้อื่น','สินค้าคงเหลือ','เงินลงทุน','ที่ดิน อาคารและอุปกรณ์','สินทรัพย์ไม่มีตัวตน','สัญญาเช่า','เจ้าหนี้การค้าและเจ้าหนี้อื่น','เงินกู้ยืม','ภาษีเงินได้','ผลประโยชน์พนักงาน','ประมาณการทางบัญชี','ทุนและส่วนของเจ้าของ','รายได้และค่าใช้จ่ายที่สำคัญ','บุคคลหรือกิจการที่เกี่ยวข้องกัน','ภาระผูกพันและหนี้สินที่อาจเกิดขึ้น','การบริหารความเสี่ยงทางการเงิน','การดำเนินงานต่อเนื่อง','เหตุการณ์ภายหลังรอบระยะเวลารายงาน','การอนุมัติงบการเงิน']
    return pd.DataFrame({'Note Topic':topics,'Status':['Pending Review']*len(topics),'Draft / Placeholder':['ข้อมูลไม่เพียงพอสำหรับสรุปอัตโนมัติ']*len(topics),'Evidence / Information Needed':['ขอข้อมูลและหลักฐานประกอบจากผู้รับผิดชอบ']*len(topics)})
