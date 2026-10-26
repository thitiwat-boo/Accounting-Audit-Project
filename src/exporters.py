from __future__ import annotations
from io import BytesIO
import re
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

REQUIRED_SHEETS=['README','Parameters','Reference_Register','TB_Original','GL_Original','TB_Normalized','GL_Normalized','Data_Quality','COA_Mapping','Grouping_Master','Unmapped_Impact','Adjusting_Entries','Adjusted_TB','D_Cash_Bank','D_AR','D_Inventory','D_PPE','D_AP','D_Borrowings','D_Equity','D_Revenue','D_Expenses','FS_Balance_Sheet','FS_Income_Statement','FS_Changes_Equity','FS_Cash_Flow','Notes_Index','Notes_Draft','Audit_Risk_Register','Audit_Workpaper','Formula_Map','Source_Traceability','Reconciliation','Change_Log']

def _safe(v):
    if pd.isna(v): return None
    if hasattr(v,'item'): 
        try: return v.item()
        except Exception: pass
    if isinstance(v,(dict,list,tuple)): return str(v)
    return v

def export_workbook(tables: dict[str,pd.DataFrame], parameters: dict, status='INCOMPLETE DRAFT') -> bytes:
    bio=BytesIO(); wb=Workbook(); ws=wb.active; ws.title='README'
    readme=[['Accounting & Audit Workbench — Red Team Build'],['Status',status],['Important','Draft for accounting review only; not an audit opinion or approved financial statements.'],['Limitation','Amounts are not considered complete unless mapping, source data, and reconciliations pass review.'],['Generated Sheets','; '.join(REQUIRED_SHEETS)]]
    for row in readme: ws.append(row)
    params=wb.create_sheet('Parameters'); params.append(['Parameter','Value'])
    for k,v in parameters.items(): params.append([k,_safe(v)])
    # Create all required sheets and write real supplied tables where available.
    for name in REQUIRED_SHEETS:
        if name in ['README','Parameters']: continue
        sh=wb.create_sheet(name); df=tables.get(name)
        if isinstance(df,pd.DataFrame) and len(df.columns):
            sh.append([str(c) for c in df.columns])
            for row in df.itertuples(index=False,name=None): sh.append([_safe(x) for x in row])
        else:
            sh.append(['Status','Detail']); sh.append(['Missing / Cannot Calculate','ไม่มีข้อมูลต้นทางหรือฟังก์ชันยังคำนวณไม่ได้; ห้ามตีความเป็นยอดศูนย์'])
    # Formula-driven Adjusted TB from TB_Normalized, with original source rows preserved.
    at=wb['Adjusted_TB']; at.delete_rows(1,at.max_row); headers=['Account Code','Account Name','Debit','Credit','Net Debit','Grouping','Sub Grouping','Account Type','FS Line Item','Reviewer Status','Source Ref']
    at.append(headers)
    norm=wb['TB_Normalized']; mapping=wb['COA_Mapping']; source=wb['TB_Original']
    if source.max_row>=2:
        # Build normalized rows using normalized table rows if supplied; formula links to normalized inputs.
        ndf=tables.get('TB_Normalized')
        if isinstance(ndf,pd.DataFrame) and len(ndf):
            for i,(_,r) in enumerate(ndf.iterrows(),start=2):
                rr=at.max_row+1
                code_col=list(ndf.columns).index('Account Code')+1 if 'Account Code' in ndf else None
                name_col=list(ndf.columns).index('Account Name')+1 if 'Account Name' in ndf else None
                debit_col=list(ndf.columns).index('Debit')+1 if 'Debit' in ndf else None
                credit_col=list(ndf.columns).index('Credit')+1 if 'Credit' in ndf else None
                at.append([f'=IFERROR(TB_Normalized!{get_column_letter(code_col)}{i},"")' if code_col else _safe(r.get('Account Code',''),),
                           f'=IFERROR(TB_Normalized!{get_column_letter(name_col)}{i},"")' if name_col else _safe(r.get('Account Name','')),
                           f'=IFERROR(TB_Normalized!{get_column_letter(debit_col)}{i},0)' if debit_col else 0,
                           f'=IFERROR(TB_Normalized!{get_column_letter(credit_col)}{i},0)' if credit_col else 0,
                           f'=C{rr}-D{rr}',
                           f'=IFERROR(XLOOKUP(A{rr},COA_Mapping!A:A,COA_Mapping!D:D,"Unmapped"),"Unmapped")',
                           f'=IFERROR(XLOOKUP(A{rr},COA_Mapping!A:A,COA_Mapping!E:E,"Unmapped"),"Unmapped")',
                           f'=IFERROR(XLOOKUP(A{rr},COA_Mapping!A:A,COA_Mapping!C:C,"Unclassified"),"Unclassified")',
                           f'=IFERROR(XLOOKUP(A{rr},COA_Mapping!A:A,COA_Mapping!G:G,"Unmapped"),"Unmapped")',
                           f'=IFERROR(XLOOKUP(A{rr},COA_Mapping!A:A,COA_Mapping!M:M,"Pending"),"Pending")',
                           f'TB_Normalized row {i}'])
    # Detail sheets sourced by approved mapping. Formula-driven amount references; values can be reviewed in Excel.
    fsmap=[('FS_Balance_Sheet','Grouping','Sub Grouping','FS Line Item',['Asset','Liability','Equity']),('FS_Income_Statement','Grouping','Sub Grouping','FS Line Item',['Revenue','Expense'])]
    formula_rows=[]
    for sheet,grp,sub,line,types in fsmap:
        sh=wb[sheet]; sh.delete_rows(1,sh.max_row); sh.append(['Grouping','Sub Grouping','Line Item','Current Year Formula','Current Year Value','Source Sheet','Source Row/Cell','Account Codes','Mapping Ref','Review Status'])
        lines=[]
        mpdf=tables.get('COA_Mapping',pd.DataFrame())
        if isinstance(mpdf,pd.DataFrame) and 'Financial Statement Line Item' in mpdf:
            for _,r in mpdf.iterrows():
                if r.get('Reviewer Status')=='Approved' and r.get('Account Type') in types and r.get('Financial Statement Line Item') not in lines: lines.append(r.get('Financial Statement Line Item'))
        for i,line_name in enumerate(lines,start=2):
            sh.append([f'=IFERROR(XLOOKUP(C{i},COA_Mapping!G:G,COA_Mapping!D:D,""),"")',f'=IFERROR(XLOOKUP(C{i},COA_Mapping!G:G,COA_Mapping!E:E,""),"")',line_name,
                       f'=SUMIFS(Adjusted_TB!$E:$E,Adjusted_TB!$I:$I,C{i},Adjusted_TB!$J:$J,"Approved")',f'=D{i}', 'Adjusted_TB',f'Adjusted_TB!E:E',
                       '; '.join(str(x) for x in mpdf.loc[(mpdf.get('Financial Statement Line Item')==line_name)&(mpdf.get('Reviewer Status')=='Approved'),'Account Code'].tolist()) if isinstance(mpdf,pd.DataFrame) and not mpdf.empty else '',
                       f'COA_Mapping line {i}','Approved mapping only'])
            formula_rows.append({'Output Sheet':sheet,'Output Cell':f'D{i}','Formula':f'=SUMIFS(Adjusted_TB!$E:$E,Adjusted_TB!$I:$I,C{i},Adjusted_TB!$J:$J,"Approved")','Source Sheet':'Adjusted_TB','Source Rows':'formula-driven','Description':line_name,'Status':'Formula written; workbook engine needed to calculate cached values'})
    fm=wb['Formula_Map']; fm.delete_rows(1,fm.max_row); fm.append(['Output Sheet','Output Cell','Formula','Source Sheet','Source Rows','Description','Status'])
    for r in formula_rows: fm.append([r[k] for k in ['Output Sheet','Output Cell','Formula','Source Sheet','Source Rows','Description','Status']])
    # Also document core row-level formulas in Adjusted_TB so users can trace normalized source values and mapping lookups.
    for rowno in range(2, at.max_row+1):
        for colno,desc in [(3,'Debit linked to TB_Normalized'),(4,'Credit linked to TB_Normalized'),(5,'Net debit = debit - credit'),(6,'Grouping lookup'),(7,'Sub Grouping lookup'),(8,'Account Type lookup'),(9,'FS line item lookup'),(10,'Reviewer status lookup')]:
            cell=f'{get_column_letter(colno)}{rowno}'
            formula=at[cell].value
            if isinstance(formula,str) and formula.startswith('='):
                fm.append(['Adjusted_TB',cell,formula,'TB_Normalized / COA_Mapping',f'row {rowno}','Source-linked formula: '+desc,'Formula written; workbook engine needed to calculate cached values'])
    # Explicitly explain unavailable statements rather than imply zero.
    for shname,reason in [('FS_Changes_Equity','Cannot Calculate: ต้องมี Opening Equity และรายการทุน/เงินปันผล/การเปลี่ยนแปลงส่วนของผู้ถือหุ้นที่ยืนยันแล้ว'),('FS_Cash_Flow','Cannot Calculate: ต้องมี cash flow classification และข้อมูลเปลี่ยนแปลงเงินสด/รายการที่ไม่ใช่เงินสดเพียงพอ')]:
        sh=wb[shname]
        if sh.max_row<=2 and sh.cell(2,1).value=='Missing / Cannot Calculate':
            sh.delete_rows(1,sh.max_row); sh.append(['Status','Reason','Required Information']); sh.append(['Cannot Calculate',reason,'Opening/closing balances, supporting schedules, transaction classifications and user confirmation'])
    # Source traceability, reconciliation, change log and details
    tr=wb['Source_Traceability']; tr.delete_rows(1,tr.max_row); tr.append(['Source Type','Source Sheet','Source Row','Account Code','Source Detail','SHA-256','Trace Status'])
    for typ,key in [('TB','TB_Original'),('GL','GL_Original')]:
        df=tables.get(key,pd.DataFrame())
        if isinstance(df,pd.DataFrame):
            for i,(_,r) in enumerate(df.iterrows(),start=2): tr.append([typ,key,i,_safe(r.get('Account Code','')),_safe(r.get('Account Name',r.get('Description',''))),parameters.get(f'{typ} SHA-256',''),f'{key}!row {i}'])
    rec=wb['Reconciliation']; rec.delete_rows(1,rec.max_row); rec.append(['Check','Formula / Value','Status','Detail'])
    rec.append(['TB Debit total','=SUM(Adjusted_TB!C:C)','Review in Excel','Formula-driven total'])
    rec.append(['TB Credit total','=SUM(Adjusted_TB!D:D)','Review in Excel','Formula-driven total'])
    rec.append(['TB Debit less Credit','=B2-B3','=IF(ABS(B4)<0.01,"PASS","FAIL")','Must be zero'])
    rec.append(['Balance Sheet equation','Not calculable unless full approved classification and retained earnings inputs available','Cannot Calculate','No artificial balancing figure'])
    cl=wb['Change_Log']; cl.delete_rows(1,cl.max_row); cl.append(['Timestamp','Project ID','Action','Object','User','Reason']); cl.append([parameters.get('Export Time',''),parameters.get('Project ID',''),'Workbook generated','Preliminary draft','Current session','Auto-generated log row'])
    # Fill actual details and audit workpaper from approved mapped accounts.
    for sheet, typ in [('D_Cash_Bank','เงินสดและรายการเทียบเท่าเงินสด'),('D_AR','ลูกหนี้การค้าและลูกหนี้อื่น'),('D_Inventory','สินค้าคงเหลือ'),('D_PPE','ที่ดิน อาคารและอุปกรณ์'),('D_AP','เจ้าหนี้การค้าและเจ้าหนี้อื่น'),('D_Borrowings','เงินกู้ยืม'),('D_Equity','ทุน'),('D_Revenue','รายได้จากการขายหรือการให้บริการ'),('D_Expenses','ค่าใช้จ่ายในการบริหาร')]:
        sh=wb[sheet]; sh.delete_rows(1,sh.max_row); sh.append(['Account Code','Account Name','Debit','Credit','Net Debit','Source Row','Mapping Status'])
        df=tables.get('TB_Normalized',pd.DataFrame()); mpdf=tables.get('COA_Mapping',pd.DataFrame())
        if isinstance(df,pd.DataFrame) and isinstance(mpdf,pd.DataFrame) and 'Financial Statement Line Item' in mpdf:
            codes=set(mpdf.loc[(mpdf['Financial Statement Line Item']==typ)&(mpdf['Reviewer Status']=='Approved'),'Account Code'].astype(str))
            for _,r in df.iterrows():
                if str(r.get('Account Code','')) in codes: sh.append([_safe(r.get('Account Code')), _safe(r.get('Account Name')), _safe(r.get('Debit')), _safe(r.get('Credit')), f'=C{sh.max_row+1}-D{sh.max_row+1}', _safe(r.get('_Source_Row')), 'Approved'])
    aw=wb['Audit_Workpaper']; aw.delete_rows(1,aw.max_row); aw.append(['WP ID','Procedure','Source Ref','Expected Evidence','Result','Conclusion','Reviewer'])
    for i,proc in enumerate(['TB debit/credit reconciliation','GL journal balance','Duplicate composite-key review','Revenue cut-off indicator','Expense cut-off indicator','Manual journal review','Related-party indicator','Suspense account review','Large transaction review'],start=1): aw.append([f'WP{i:03d}',proc,'See Source_Traceability','Source documents and approval evidence','Not performed / requires reviewer','Pending Review',''])
    # Style, widths, formulas sanity check
    for sh in wb.worksheets:
        sh.freeze_panes='A2'; sh.auto_filter.ref=sh.dimensions
        for cell in sh[1]: cell.font=Font(bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='1F5A94'); cell.alignment=Alignment(wrap_text=True,vertical='top')
        for col in sh.columns:
            letter=get_column_letter(col[0].column); lengths=[len(str(c.value or '')) for c in list(col)[:250]]
            sh.column_dimensions[letter].width=min(max(max(lengths+[10])+2,12),45)
    # Verify sheet names and formulas do not contain broken refs; formulas may not have cached values until opened in Excel/LibreOffice.
    bio=BytesIO(); wb.save(bio); payload=bio.getvalue()
    check=load_workbook(BytesIO(payload),data_only=False)
    if not set(REQUIRED_SHEETS).issubset(set(check.sheetnames)): raise ValueError('Required sheet missing from export')
    for sh in check.worksheets:
        for row in sh.iter_rows():
            for cell in row:
                if isinstance(cell.value,str) and cell.value.startswith('=') and '#REF!' in cell.value: raise ValueError(f'Broken formula reference at {sh.title}!{cell.coordinate}')
    return payload
