from __future__ import annotations
import pandas as pd

KEYWORDS = [
 ("เงินสด","สินทรัพย์หมุนเวียน","เงินสดและรายการเทียบเท่าเงินสด","Asset"),
 ("ธนาคาร","สินทรัพย์หมุนเวียน","เงินสดและรายการเทียบเท่าเงินสด","Asset"),
 ("ลูกหนี้","สินทรัพย์หมุนเวียน","ลูกหนี้การค้าและลูกหนี้อื่น","Asset"),
 ("สินค้าคงเหลือ","สินทรัพย์หมุนเวียน","สินค้าคงเหลือ","Asset"),
 ("ที่ดิน","สินทรัพย์ไม่หมุนเวียน","ที่ดิน อาคารและอุปกรณ์","Asset"),
 ("อาคาร","สินทรัพย์ไม่หมุนเวียน","ที่ดิน อาคารและอุปกรณ์","Asset"),
 ("อุปกรณ์","สินทรัพย์ไม่หมุนเวียน","ที่ดิน อาคารและอุปกรณ์","Asset"),
 ("เจ้าหนี้","หนี้สินหมุนเวียน","เจ้าหนี้การค้าและเจ้าหนี้อื่น","Liability"),
 ("เงินกู้","หนี้สิน","เงินกู้ยืม","Liability"),
 ("ทุน","ส่วนของเจ้าของ","ทุน","Equity"),
 ("กำไรสะสม","ส่วนของเจ้าของ","กำไรสะสม","Equity"),
 ("รายได้","รายได้","รายได้จากการขายหรือการให้บริการ","Revenue"),
 ("ขาย","รายได้","รายได้จากการขายหรือการให้บริการ","Revenue"),
 ("ต้นทุน","ค่าใช้จ่าย","ต้นทุนขายหรือต้นทุนการให้บริการ","Expense"),
 ("ค่าใช้จ่าย","ค่าใช้จ่าย","ค่าใช้จ่ายในการบริหาร","Expense"),
 ("เงินเดือน","ค่าใช้จ่าย","ค่าใช้จ่ายในการบริหาร","Expense"),
 ("ดอกเบี้ย","ค่าใช้จ่าย","ค่าใช้จ่ายทางการเงิน","Expense"),
 ("ภาษีเงินได้","ค่าใช้จ่าย","ภาษีเงินได้","Expense"),
]
def suggest_mapping(tb: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for _, r in tb.iterrows():
        name=str(r.get("Account Name",""))
        match=None
        for keyword, section, line, typ in KEYWORDS:
            if keyword in name:
                match=(section,line,typ,keyword); break
        if match:
            section,line,typ,keyword=match
            method="AI Suggested"
            reason=f"ชื่อบัญชีมีคำว่า '{keyword}'"
            confidence=0.65
        else:
            section,line,typ="ต้องสอบทาน","ยังไม่จัดประเภท","Memo"
            method="Unmapped"; reason="ไม่พบกฎจากชื่อบัญชีที่ตรงกัน"; confidence=0.0
        rows.append({
          "Account Code":r.get("Account Code",""),"Account Name":name,
          "Grouping":section,"Financial Statement Line Item":line,"Account Type":typ,
          "Mapping Method":method,"Confidence Score":confidence,
          "Reviewer Status":"Pending","Reviewer Comment":reason,
          "Source Row":r.get("_Source_Row","")
        })
    return pd.DataFrame(rows)
