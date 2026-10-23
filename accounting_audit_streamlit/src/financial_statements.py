from __future__ import annotations
import pandas as pd

def build_statement(tb: pd.DataFrame, mapping: pd.DataFrame):
    """Draft statements only. No unresolved account is silently included in totals."""
    if tb.empty or mapping.empty:
        return {"balance_sheet":pd.DataFrame(), "income_statement":pd.DataFrame(),
                "warnings":["ต้องนำเข้า TB และ Mapping ก่อน"]}
    data=tb.copy()
    mp=mapping[["Account Code","Grouping","Financial Statement Line Item","Account Type","Reviewer Status"]].copy()
    data["Account Code"]=data["Account Code"].astype(str)
    mp["Account Code"]=mp["Account Code"].astype(str)
    data=data.merge(mp,on="Account Code",how="left",suffixes=("","_map"))
    data["Debit"]=pd.to_numeric(data.get("Debit",0),errors="coerce").fillna(0)
    data["Credit"]=pd.to_numeric(data.get("Credit",0),errors="coerce").fillna(0)
    data["Net Debit"]=data["Debit"]-data["Credit"]
    data["Presentation Amount"]=data["Net Debit"]
    data.loc[data["Account Type"].isin(["Liability","Equity","Revenue"]),"Presentation Amount"] *= -1
    approved=data[data["Reviewer Status"].eq("Approved")].copy()
    unresolved=data[~data["Reviewer Status"].eq("Approved")].copy()
    bs_types=["Asset","Liability","Equity"]
    bs=approved[approved["Account Type"].isin(bs_types)].groupby(
       ["Grouping","Financial Statement Line Item"],dropna=False)["Presentation Amount"].sum().reset_index()
    bs=bs.rename(columns={"Presentation Amount":"Draft Amount"})
    inc=approved[approved["Account Type"].isin(["Revenue","Expense"])].groupby(
       ["Grouping","Financial Statement Line Item"],dropna=False)["Presentation Amount"].sum().reset_index()
    inc=inc.rename(columns={"Presentation Amount":"Draft Amount"})
    warnings=[]
    if len(unresolved):
        warnings.append(f"มี {len(unresolved)} บัญชีที่ยังไม่ได้ Approved จึงไม่รวมในยอดงบ")
    deb=float(data["Debit"].sum()); cred=float(data["Credit"].sum())
    if abs(deb-cred)>=0.01: warnings.append(f"TB ไม่สมดุล: เดบิต-เครดิต = {deb-cred:,.2f}")
    warnings.append("ยอดในงบเป็นร่างตาม Mapping ที่ผู้ใช้ Approved เท่านั้น ต้องสอบทานการจัดประเภทและยอดคงเหลือ")
    return {"balance_sheet":bs,"income_statement":inc,"unmapped_or_pending":unresolved,
            "warnings":warnings,"normalized_tb":data}

def draft_notes_checklist():
    topics=[
      "ข้อมูลทั่วไปของกิจการ","เกณฑ์การจัดทำงบการเงิน","นโยบายการบัญชีที่สำคัญ",
      "เงินสดและรายการเทียบเท่าเงินสด","ลูกหนี้การค้าและลูกหนี้อื่น","สินค้าคงเหลือ",
      "เงินลงทุน","ที่ดิน อาคารและอุปกรณ์","สินทรัพย์ไม่มีตัวตน","สัญญาเช่า",
      "เจ้าหนี้การค้าและเจ้าหนี้อื่น","เงินกู้ยืม","ภาษีเงินได้","ผลประโยชน์พนักงาน",
      "ประมาณการทางบัญชี","ทุนและส่วนของเจ้าของ","รายได้และค่าใช้จ่ายที่สำคัญ",
      "บุคคลหรือกิจการที่เกี่ยวข้องกัน","ภาระผูกพันและหนี้สินที่อาจเกิดขึ้น",
      "การบริหารความเสี่ยงทางการเงิน","การดำเนินงานต่อเนื่อง",
      "เหตุการณ์ภายหลังรอบระยะเวลารายงาน","การอนุมัติงบการเงิน"]
    return pd.DataFrame({"Note Topic":topics,"Status":["Requires management input"]*len(topics),
                         "Draft / Placeholder":["[รอข้อมูลจากฝ่ายบริหาร]"]*len(topics),
                         "Evidence / Information Needed":["ระบุข้อมูลและหลักฐานที่เกี่ยวข้อง"]*len(topics)})
