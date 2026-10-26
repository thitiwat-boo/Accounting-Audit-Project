from __future__ import annotations
import hashlib, json, uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
import pandas as pd
import streamlit as st
from src.loaders import read_excel_sheets, suggest_columns, normalize_columns, TB_ALIASES, GL_ALIASES
from src.validators import tb_quality, gl_quality, duplicate_gl_rows
from src.mapping import suggest_mapping
from src.financial_statements import build_statement, draft_notes_checklist
from src.audit_tests import create_risk_register
from src.exporters import export_workbook

st.set_page_config(page_title='Accounting & Audit Workbench', page_icon='📊', layout='wide')
if 'project_id' not in st.session_state: st.session_state.project_id = 'AAW-' + uuid.uuid4().hex[:8].upper()
if 'mapping_approval_log' not in st.session_state: st.session_state.mapping_approval_log=[]
if 'adjusting_entries' not in st.session_state: st.session_state.adjusting_entries=pd.DataFrame(columns=['Date','JE No','Account Code','Account Name','Debit','Credit','Description','Approved','Source Ref'])

st.title('Accounting & Audit Workbench')
st.caption('Red Team build — งบฉบับร่างเพื่อการสอบทานเท่านั้น ไม่ใช่การรับรองงบหรือความเห็นผู้สอบบัญชี')
with st.sidebar:
    st.header('1. Project Setup')
    st.text_input('Project ID', key='project_id', disabled=True)
    entity=st.text_input('ชื่อนิติบุคคล','ตัวอย่าง บริษัท จำกัด')
    entity_type=st.selectbox('ประเภทนิติบุคคล',['บริษัทจำกัด','บริษัทมหาชนจำกัด','ห้างหุ้นส่วนจดทะเบียน','อื่น ๆ'])
    framework=st.selectbox('กรอบรายงานทางการเงิน',['TFRS for NPAEs','TFRS for PAEs / TFRS เต็มรูปแบบ','กรอบอื่นที่ผู้ใช้กำหนด','Management Reporting'])
    period_end=st.date_input('วันสิ้นงวด', value=pd.Timestamp('2025-12-31').date())
    prior_period=st.text_input('งวดเปรียบเทียบ (ถ้ามี)','')
    currency=st.selectbox('หน่วยเงิน',['บาท','พันบาท','ล้านบาท'])
    materiality=st.number_input('Materiality (บาท)',min_value=0.0,value=100000.0,step=10000.0)
    risk_level=st.selectbox('ระดับความเสี่ยง',['ต่ำ','ปานกลาง','สูง'])
    st.info('Privacy: ใช้ข้อมูลตัวอย่างก่อน ห้าม Upload TB/GL จริงลงพื้นที่สาธารณะ และดาวน์โหลด Project State เก็บไว้เอง')

st.markdown('### Workflow')
st.caption('1 Setup → 2 Upload → 3 Validate → 4 Mapping → 5 Adjustments → 6 Financial Statements → 7 Notes → 8 Audit Workpaper → 9 Export')

# Capture uploaded file bytes immediately; subsequent reruns parse from session bytes, not only UploadedFile objects.
def file_control(label, prefix, types):
    up=st.file_uploader(label, type=types, key=f'{prefix}_uploader')
    if up is not None:
        raw=up.getvalue(); digest=hashlib.sha256(raw).hexdigest()
        old=st.session_state.get(f'{prefix}_sha256')
        if old != digest:
            st.session_state[f'{prefix}_bytes']=raw; st.session_state[f'{prefix}_filename']=up.name
            st.session_state[f'{prefix}_sha256']=digest; st.session_state[f'{prefix}_upload_time']=datetime.now().isoformat(timespec='seconds')
            st.session_state.pop(f'{prefix}_normalized',None)
            if prefix=='tb': st.session_state.pop('coa_mapping',None)
            st.session_state.pop('statements',None)
    if st.session_state.get(f'{prefix}_bytes'):
        st.success(f"{label}: {st.session_state.get(f'{prefix}_filename')} | SHA-256: {st.session_state.get(f'{prefix}_sha256')}")
        st.caption(f"Upload time: {st.session_state.get(f'{prefix}_upload_time','')} | bytes: {len(st.session_state[f'{prefix}_bytes']):,}")
    return st.session_state.get(f'{prefix}_bytes')

st.header('2. Upload and Lock Inputs')
c1,c2=st.columns(2)
with c1: tb_bytes=file_control('TB Excel จาก PEAK','tb',['xlsx','xlsm'])
with c2: gl_bytes=file_control('GL Excel','gl',['xlsx','xlsm'])

def parse_and_normalize(raw, key, aliases):
    if not raw: return None
    sheets=read_excel_sheets(BytesIO(raw))
    sheet_key=f'{key}_sheet_name'
    default=st.session_state.get(sheet_key, list(sheets.keys())[0])
    selected=st.selectbox(f'เลือก Sheet {key.upper()}',list(sheets.keys()),index=list(sheets.keys()).index(default) if default in sheets else 0,key=f'{key}_sheet_select')
    st.session_state[sheet_key]=selected
    df=sheets[selected]
    st.caption(f'{key.upper()} source sheet: {selected}; rows={len(df):,}; columns={len(df.columns)}')
    with st.expander(f'Preview {key.upper()}',expanded=False): st.dataframe(df.head(10),use_container_width=True)
    suggestions=suggest_columns(df.columns,aliases); options=['— ไม่ใช้ —']+list(df.columns); colmap={}
    cols=st.columns(2)
    for i,(target,source) in enumerate(suggestions.items()):
        with cols[i%2]:
            default=source if source in df.columns else '— ไม่ใช้ —'
            choice=st.selectbox(f'{key.upper()} → {target}',options,index=options.index(default),key=f'{key}_{selected}_{target}_col')
            colmap[target]=None if choice=='— ไม่ใช้ —' else choice
    normalized=normalize_columns(df,colmap)
    st.session_state[f'{key}_normalized']=normalized
    st.session_state[f'{key}_sheet']=selected
    st.session_state[f'{key}_row_count']=len(df)
    st.session_state[f'{key}_column_mapping']=colmap
    return normalized

with st.expander('Column Mapping and Normalization',expanded=bool(tb_bytes or gl_bytes)):
    t1,t2=st.tabs(['TB','GL'])
    with t1: tb=parse_and_normalize(tb_bytes,'tb',TB_ALIASES) if tb_bytes else None
    with t2: gl=parse_and_normalize(gl_bytes,'gl',GL_ALIASES) if gl_bytes else None
# Keep data available when tab reruns / users navigate.
tb=st.session_state.get('tb_normalized'); gl=st.session_state.get('gl_normalized')

if st.button('Clear current project session', type='secondary'):
    for k in list(st.session_state.keys()):
        if k not in ['project_id']: del st.session_state[k]
    st.session_state.project_id='AAW-'+uuid.uuid4().hex[:8].upper(); st.rerun()

st.header('3. Data Validation')
if tb is not None:
    q=tb_quality(tb); st.subheader('TB Quality'); st.dataframe(q,use_container_width=True)
    st.session_state['tb_quality']=q
    st.metric('TB Debit less Credit',f"{pd.to_numeric(tb.get('Debit',pd.Series(dtype=float)),errors='coerce').fillna(0).sum()-pd.to_numeric(tb.get('Credit',pd.Series(dtype=float)),errors='coerce').fillna(0).sum():,.2f}")
if gl is not None:
    gq=gl_quality(gl); st.subheader('GL Quality'); st.dataframe(gq,use_container_width=True); st.session_state['gl_quality']=gq
    dups=duplicate_gl_rows(gl)
    st.caption(f'รายการที่เหมือนกันตาม composite key: {len(dups)} แถว — เลขที่เอกสารซ้ำเพียงอย่างเดียวไม่ถือว่า duplicate')
    if not dups.empty:
        with st.expander('ดูรายการที่ควรสอบทาน'): st.dataframe(dups,use_container_width=True)

st.header('4. COA Mapping Review')
if tb is not None and {'Account Code','Account Name'}.issubset(tb.columns):
    if 'coa_mapping' not in st.session_state:
        st.session_state.coa_mapping=suggest_mapping(tb)
    mapping=st.session_state.coa_mapping.copy()
    # Ensure current account list and mapping keys correspond to the uploaded TB.
    mapping=mapping.drop_duplicates('Account Code',keep='last')
    edited=st.data_editor(mapping,use_container_width=True,num_rows='fixed',key='mapping_editor',
        column_config={'Account Type':st.column_config.SelectboxColumn(options=['Asset','Liability','Equity','Revenue','Expense','Unclassified']),
                       'Reviewer Status':st.column_config.SelectboxColumn(options=['Pending','Approved','Rejected']),
                       'Confidence':st.column_config.NumberColumn(min_value=0,max_value=1,step=.05)},
        disabled=['Account Code','Account Name','Mapping Method','Confidence','Source Row'])
    c1,c2,c3,c4=st.columns(4)
    with c1:
        if st.button('Save Mapping edits'):
            st.session_state.coa_mapping=edited; st.session_state['mapping_saved_at']=datetime.now().isoformat(timespec='seconds'); st.success('บันทึก Mapping ใน Session แล้ว')
    with c2:
        if st.button('Approve All Safe Suggestions'):
            safe=edited.copy(); unsafe=safe['Confidence'].lt(.7) | safe['Account Name'].astype(str).str.contains(r'suspense|พักบัญชี|memo|contra|ภาษี|กรรมการ|ผู้ถือหุ้น|related party|ระหว่างกัน',case=False,regex=True)
            safe.loc[~unsafe & safe['Account Type'].ne('Unclassified'),'Reviewer Status']='Approved'
            safe.loc[unsafe,'Reviewer Status']='Pending'; safe['Reviewer']=entity; safe['Reviewed Date']=datetime.now().isoformat(timespec='seconds')
            st.session_state.coa_mapping=safe; st.session_state.mapping_approval_log.append({'time':datetime.now().isoformat(timespec='seconds'),'action':'Approve All Safe Suggestions','user':entity,'count':int((~unsafe).sum())}); st.rerun()
    with c3:
        if st.button('Reset all to Pending'):
            edited['Reviewer Status']='Pending'; edited['Reviewer']=''; edited['Reviewed Date']=''; st.session_state.coa_mapping=edited; st.session_state.pop('statements',None); st.rerun()
    with c4:
        csv=edited.to_csv(index=False).encode('utf-8-sig'); st.download_button('Export Mapping CSV',csv,'COA_Mapping.csv','text/csv')
    approved_count=int(edited['Reviewer Status'].eq('Approved').sum()); pending_count=int((~edited['Reviewer Status'].eq('Approved')).sum())
    st.write(f'Approved: **{approved_count}** | Pending/Rejected: **{pending_count}**')
    imp=edited[~edited['Reviewer Status'].eq('Approved')].copy()
    if not imp.empty:
        st.warning(f'BLOCKED: ยังไม่พร้อมสร้างงบที่ดูเหมือนสมบูรณ์ — มี {len(imp)} บัญชี Pending/Rejected')
        st.dataframe(imp[['Account Code','Account Name','Grouping','Sub Grouping','Financial Statement Line Item','Reviewer Status','Comment']],use_container_width=True)
    st.session_state.coa_mapping=edited
    # Import Mapping CSV
    with st.expander('Import previously reviewed Mapping CSV'):
        mapping_file=st.file_uploader('เลือก Mapping CSV',type=['csv'],key='mapping_import')
        if mapping_file and st.button('Import Mapping'):
            incoming=pd.read_csv(mapping_file,dtype={'Account Code':str})
            if {'Account Code','Grouping','Sub Grouping','Reviewer Status'}.issubset(incoming.columns):
                st.session_state.coa_mapping=incoming; st.success('นำเข้า Mapping แล้ว; กรุณาตรวจสอบก่อนใช้งาน'); st.rerun()
            else: st.error('ไฟล์ Mapping ขาดคอลัมน์สำคัญ')
else:
    st.info('ต้องนำเข้า TB และจับคู่ Account Code / Account Name ก่อนเสนอ Mapping')

st.header('5. Adjusting Entries')
st.caption('ยังไม่มีรายการปรับปรุงก็สร้าง Adjusted TB ได้จาก TB เดิม แต่รายการปรับปรุงใหม่ต้องมีผู้ใช้ยืนยันและต้องไม่ถูกนำไปรวมเงียบ ๆ')
with st.expander('บันทึก Adjusting Entry',expanded=False):
    with st.form('adjustment_form'):
        adate=st.date_input('วันที่ปรับปรุง',value=period_end); aje=st.text_input('JE No'); acode=st.text_input('Account Code'); aname=st.text_input('Account Name'); adebit=st.number_input('Debit',min_value=0.0); acredit=st.number_input('Credit',min_value=0.0); adesc=st.text_input('Description'); aok=st.checkbox('ผู้ใช้ยืนยันรายการนี้แล้ว')
        submit=st.form_submit_button('เพิ่ม Adjusting Entry')
        if submit:
            if abs(adebit-acredit)>0.009: st.error('รายการปรับปรุงต้องเดบิตเท่ากับเครดิตก่อนบันทึกเป็นชุดรายการ')
            elif not aok: st.error('ต้องยืนยันรายการก่อน')
            else:
                row=pd.DataFrame([{'Date':str(adate),'JE No':aje,'Account Code':acode,'Account Name':aname,'Debit':adebit,'Credit':acredit,'Description':adesc,'Approved':True,'Source Ref':'User input'}]); st.session_state.adjusting_entries=pd.concat([st.session_state.adjusting_entries,row],ignore_index=True); st.success('เพิ่มรายการแล้ว')
st.dataframe(st.session_state.adjusting_entries,use_container_width=True)

st.header('6. Financial Statements')
if tb is not None and 'coa_mapping' in st.session_state:
    if st.button('Build Draft Statements',type='primary'):
        st.session_state.statements=build_statement(tb,st.session_state.coa_mapping,st.session_state.adjusting_entries)
    if 'statements' in st.session_state:
        result=st.session_state.statements
        if result.get('blocked'): st.error('BLOCKED / INCOMPLETE DRAFT — แก้ไข Data Quality และอนุมัติ Mapping ที่จำเป็นก่อนใช้เป็นงบ')
        else: st.warning('DRAFT — ต้องสอบทานยอดและการจัดประเภทก่อนใช้งาน')
        for w in result.get('warnings',[]): st.warning(w)
        tab1,tab2,tab3=st.tabs(['งบแสดงฐานะการเงิน (Draft)','งบกำไรขาดทุน (Draft)','Unmapped Impact'])
        with tab1: st.dataframe(result['balance_sheet'],use_container_width=True)
        with tab2: st.dataframe(result['income_statement'],use_container_width=True)
        with tab3: st.dataframe(result['unmapped_or_pending'],use_container_width=True)
        st.info('งบเปลี่ยนแปลงส่วนของผู้ถือหุ้นและงบกระแสเงินสดจะเป็น Cannot Calculate จนกว่าจะมีข้อมูลต้นงวด/รายการเปลี่ยนแปลงและการจัดประเภทกระแสเงินสดเพียงพอ')
else: st.info('นำเข้า TB และ Mapping ก่อน')

st.header('7. Notes Draft')
notes=draft_notes_checklist(); st.dataframe(notes,use_container_width=True)

st.header('8. Audit Workpaper & Risk Register')
if gl is not None:
    risks=create_risk_register(gl,str(period_end),materiality); st.dataframe(risks,use_container_width=True); st.session_state.audit_risks=risks
else: risks=pd.DataFrame(columns=['Risk ID','Account','Amount','Assertion','Risk Reason','Rule Triggered','Suggested Procedure','Evidence Needed','Source Ref','Risk Rating','Owner','Status','Conclusion']); st.info('อัปโหลด GL เพื่อสร้าง Risk Indicators; รายการเสี่ยงไม่ใช่ข้อสรุปว่ามีทุจริต')

st.header('9. Export and Project State')
# Download a restorable JSON snapshot of state metadata + normalized tables; raw source bytes are not exported unless user explicitly requests state export.
state_obj={'project_id':st.session_state.project_id,'entity':entity,'entity_type':entity_type,'framework':framework,'period_end':str(period_end),'tb_filename':st.session_state.get('tb_filename'),'tb_sha256':st.session_state.get('tb_sha256'),'gl_filename':st.session_state.get('gl_filename'),'gl_sha256':st.session_state.get('gl_sha256'),'mapping_approval_log':st.session_state.mapping_approval_log}
st.download_button('Download Project State (metadata JSON)',json.dumps(state_obj,ensure_ascii=False,indent=2).encode('utf-8'),'project_state_metadata.json','application/json')
if tb is not None:
    params={'Project ID':st.session_state.project_id,'Entity':entity,'Entity Type':entity_type,'Framework':framework,'Period End':str(period_end),'Prior Period':prior_period,'Currency':currency,'Materiality':materiality,'Risk Level':risk_level,'TB Filename':st.session_state.get('tb_filename',''),'TB SHA-256':st.session_state.get('tb_sha256',''),'TB Upload Time':st.session_state.get('tb_upload_time',''),'TB Sheet':st.session_state.get('tb_sheet',''),'GL Filename':st.session_state.get('gl_filename',''),'GL SHA-256':st.session_state.get('gl_sha256',''),'GL Upload Time':st.session_state.get('gl_upload_time',''),'GL Sheet':st.session_state.get('gl_sheet',''),'Export Time':datetime.now().isoformat(timespec='seconds'),'Status':'INCOMPLETE DRAFT'}
    tables={'TB_Original':tb,'TB_Normalized':tb,'Data_Quality':st.session_state.get('tb_quality',pd.DataFrame()),'COA_Mapping':st.session_state.get('coa_mapping',pd.DataFrame()),'Adjusting_Entries':st.session_state.adjusting_entries,'Notes_Draft':notes,'Notes_Index':notes,'Audit_Risk_Register':risks,'Audit_Workpaper':pd.DataFrame([{'WP ID':'WP001','Procedure':'TB balance','Result':'Pending validation','Conclusion':'Pending review'}])}
    if gl is not None: tables.update({'GL_Original':gl,'GL_Normalized':gl,'Duplicate_Journal_Review':duplicate_gl_rows(gl),'Data_Quality':pd.concat([st.session_state.get('tb_quality',pd.DataFrame()).assign(Source='TB'),st.session_state.get('gl_quality',pd.DataFrame()).assign(Source='GL')],ignore_index=True)})
    if 'statements' in st.session_state:
        sr=st.session_state.statements; tables.update({'FS_Balance_Sheet':sr['balance_sheet'],'FS_Income_Statement':sr['income_statement'],'Unmapped_Impact':sr['unmapped_or_pending']})
    blob=export_workbook(tables,params,status='INCOMPLETE DRAFT — review required')
    st.download_button('Download Preliminary Data, Mapping & Draft FS Workbook (.xlsx)',blob,'Accounting_Audit_Workbench_DRAFT.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
else: st.info('ต้อง Upload TB ก่อนจึงจะ Export workbook ได้')

st.caption('Rule-based mapping is a proposal, not an accounting conclusion. Confirm the current DBD abbreviated financial statement format and applicable accounting framework before finalizing line-item mappings.')
