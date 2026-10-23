import streamlit as st
import pandas as pd
import plotly.express as px
from src.loaders import read_excel_sheets, suggest_columns, normalize_columns, TB_ALIASES, GL_ALIASES
from src.validators import tb_quality, gl_quality
from src.mapping import suggest_mapping
from src.financial_statements import build_statement, draft_notes_checklist
from src.audit_tests import duplicate_gl_rows, create_risk_register
from src.exporters import export_workbook

st.set_page_config(page_title="Accounting & Audit Workbench",page_icon="📊",layout="wide")
st.title("Accounting, Financial Statements & Audit Workbench")
st.caption("ระบบช่วยเตรียมข้อมูลและร่างเอกสารจาก TB/GL — ไม่ใช่การรับรองงบหรือรายงานผู้สอบบัญชี")
with st.sidebar:
    st.header("ตั้งค่ากิจการและงวด")
    entity=st.text_input("ชื่อนิติบุคคล", "ตัวอย่าง บริษัท จำกัด")
    entity_type=st.selectbox("ประเภทนิติบุคคล",["บริษัทจำกัด","บริษัทมหาชนจำกัด","ห้างหุ้นส่วนจดทะเบียน","อื่น ๆ"])
    framework=st.selectbox("กรอบรายงานทางการเงิน",["TFRS for NPAEs","TFRS for PAEs / TFRS เต็มรูปแบบ","กรอบอื่นที่ผู้ใช้กำหนด","Management Reporting"])
    period=st.text_input("รอบบัญชี", "ปีสิ้นสุด 31/12/2568")
    period_end=st.date_input("วันสิ้นงวด", value=pd.Timestamp("2025-12-31").date())
    currency=st.selectbox("หน่วยแสดงผล",["บาท","พันบาท","ล้านบาท"])
    lang=st.selectbox("ภาษา",["ไทย","ไทย/English"])
    materiality=st.number_input("Materiality เบื้องต้น (บาท)",min_value=0.0,value=100000.0,step=10000.0)
    st.info("ข้อมูลใน Community Cloud อาจหายเมื่อ session/instance reset โปรดดาวน์โหลดผลลัพธ์และ configuration เก็บไว้")
st.subheader("1. นำเข้า TB และ GL")
c1,c2=st.columns(2)
with c1:
    tb_file=st.file_uploader("อัปโหลด Trial Balance (.xlsx)",type=["xlsx"],key="tb")
with c2:
    gl_file=st.file_uploader("อัปโหลด General Ledger (.xlsx)",type=["xlsx"],key="gl")
template_path = __import__("pathlib").Path(__file__).parent / "templates" / "TB_GL_Template.xlsx"
st.download_button("ดาวน์โหลด Template TB/GL", data=template_path.read_bytes(),
                   file_name="TB_GL_Template.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
def upload_and_map(file, aliases, key):
    if not file: return None
    sheets=read_excel_sheets(file)
    sh=st.selectbox(f"เลือก Sheet — {key}",list(sheets.keys()),key=f"{key}_sheet")
    df=sheets[sh]
    st.caption(f"ตัวอย่างข้อมูลจาก Sheet: {sh}")
    st.dataframe(df.head(8),use_container_width=True)
    suggestions=suggest_columns(df.columns,aliases)
    st.markdown("**จับคู่คอลัมน์**")
    mapping={}
    cols=["— ไม่ใช้ —"]+list(df.columns)
    for target,source in suggestions.items():
        default=source if source in df.columns else "— ไม่ใช้ —"
        choice=st.selectbox(target,cols,index=cols.index(default),key=f"{key}_{target}")
        mapping[target]=None if choice=="— ไม่ใช้ —" else choice
    normalized=normalize_columns(df,mapping)
    return normalized
tb=None; gl=None
if tb_file:
    with st.expander("ตรวจสอบ/จับคู่คอลัมน์ TB",expanded=True):
        tb=upload_and_map(tb_file,TB_ALIASES,"TB")
if gl_file:
    with st.expander("ตรวจสอบ/จับคู่คอลัมน์ GL",expanded=True):
        gl=upload_and_map(gl_file,GL_ALIASES,"GL")
if tb is not None:
    st.subheader("2. Data Quality")
    st.dataframe(tb_quality(tb),use_container_width=True)
if gl is not None:
    st.dataframe(gl_quality(gl),use_container_width=True)
    dups=duplicate_gl_rows(gl)
    with st.expander(f"รายการ GL ที่อาจซ้ำ ({len(dups)})"):
        st.dataframe(dups,use_container_width=True)
if tb is not None and "Account Code" in tb and "Account Name" in tb:
    st.subheader("3. Mapping บัญชี — กรุณาตรวจสอบและกดยืนยัน")
    mapping=suggest_mapping(tb)
    edited=st.data_editor(mapping,use_container_width=True,num_rows="dynamic",key="mapping_editor",
       column_config={"Reviewer Status":st.column_config.SelectboxColumn(options=["Pending","Approved","Rejected"]),
                      "Confidence Score":st.column_config.NumberColumn(min_value=0,max_value=1,step=0.05)})
    st.session_state["mapping"]=edited
    st.caption("การเสนอ Mapping จากชื่อบัญชีเป็นเพียงข้อเสนอ ไม่ใช่ข้อสรุปทางวิชาชีพ")
    if st.button("สร้างงบฉบับร่างจาก Mapping ที่ Approved",type="primary"):
        st.session_state["statements"]=build_statement(tb,edited)
        st.session_state["notes"]=draft_notes_checklist()
if "statements" in st.session_state:
    result=st.session_state["statements"]
    st.subheader("4. งบการเงินฉบับร่าง")
    for w in result.get("warnings",[]): st.warning(w)
    t1,t2,t3=st.tabs(["งบฐานะการเงิน","งบกำไรขาดทุน","บัญชีรอตรวจสอบ"])
    with t1: st.dataframe(result["balance_sheet"],use_container_width=True)
    with t2: st.dataframe(result["income_statement"],use_container_width=True)
    with t3: st.dataframe(result.get("unmapped_or_pending",pd.DataFrame()),use_container_width=True)
    st.subheader("5. หมายเหตุประกอบงบ — Checklist")
    st.dataframe(st.session_state["notes"],use_container_width=True)
if gl is not None:
    st.subheader("6. Audit Risk Register (Suggested)")
    risks=create_risk_register(gl,str(period_end))
    st.dataframe(risks,use_container_width=True)
    if not risks.empty:
        st.plotly_chart(px.bar(risks,x="Risk ID",y="Risk Score",color="Risk Level",title="รายการเสี่ยงที่ควรสอบทาน"),use_container_width=True)
if tb is not None:
    tables={"TB_Original":tb,"Data_Quality":tb_quality(tb)}
    if gl is not None:
        tables.update({"GL_Original":gl,"GL_Duplicates":duplicate_gl_rows(gl),
                       "Audit_Risk_Register":create_risk_register(gl,str(period_end))})
    if "mapping" in st.session_state: tables["COA_Mapping"]=st.session_state["mapping"]
    if "statements" in st.session_state:
        sr=st.session_state["statements"]
        tables.update({"FS_Balance_Sheet":sr["balance_sheet"],"FS_Income_Statement":sr["income_statement"],
                       "Unmapped_Accounts":sr.get("unmapped_or_pending",pd.DataFrame()),
                       "Notes_Index":st.session_state.get("notes",pd.DataFrame())})
    params={"Entity":entity,"Entity Type":entity_type,"Framework":framework,"Period":period,
            "Period End":str(period_end),"Currency":currency,"Language":lang,"Materiality":materiality,
            "Status":"DRAFT"}
    blob=export_workbook(tables,params)
    st.download_button("ดาวน์โหลด Accounting & Audit Pack (.xlsx)",data=blob,
                       file_name="Accounting_Audit_Pack_DRAFT.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
st.divider()
st.caption("ข้อจำกัด: ต้องใช้ supporting schedules และการยืนยันจากผู้ใช้สำหรับการจัดประเภท ภาษี กระแสเงินสด หมายเหตุ และข้อสรุปทางวิชาชีพ ระบบนี้ไม่สร้างความเห็นผู้สอบบัญชีอัตโนมัติ")
