from __future__ import annotations
import re
import pandas as pd

# Transparent rules, not an AI model. Suggestions always require human approval.
RULES = [
    (r'เงินสด|เงินฝากธนาคาร|cash|bank', 'สินทรัพย์หมุนเวียน', 'เงินสดและรายการเทียบเท่าเงินสด', 'Asset', 'งบแสดงฐานะการเงิน', 'เงินสดและรายการเทียบเท่าเงินสด', 'Operating', .88),
    (r'ลูกหนี้การค้า|ลูกหนี้ค้างรับ|accounts receivable|trade receivable', 'สินทรัพย์หมุนเวียน', 'ลูกหนี้การค้าและลูกหนี้อื่น', 'Asset', 'งบแสดงฐานะการเงิน', 'ลูกหนี้การค้าและลูกหนี้อื่น', 'Operating', .82),
    (r'ลูกหนี้อื่น|เงินทดรองจ่าย|เงินให้กู้ยืมระยะสั้น', 'สินทรัพย์หมุนเวียน', 'ลูกหนี้การค้าและลูกหนี้อื่น', 'Asset', 'งบแสดงฐานะการเงิน', 'ลูกหนี้การค้าและลูกหนี้อื่น', 'Operating', .72),
    (r'สินค้าคงเหลือ|inventory|stock', 'สินทรัพย์หมุนเวียน', 'สินค้าคงเหลือ', 'Asset', 'งบแสดงฐานะการเงิน', 'สินค้าคงเหลือ', 'Operating', .9),
    (r'ค่าใช้จ่ายจ่ายล่วงหน้า|ภาษีซื้อรอขอคืน|สินทรัพย์หมุนเวียนอื่น', 'สินทรัพย์หมุนเวียน', 'สินทรัพย์หมุนเวียนอื่น', 'Asset', 'งบแสดงฐานะการเงิน', 'สินทรัพย์หมุนเวียนอื่น', 'Operating', .7),
    (r'ที่ดิน|อาคาร|อุปกรณ์|เครื่องใช้สำนักงาน|ยานพาหนะ|ค่าเสื่อมราคาสะสม|สินทรัพย์ถาวร|property plant equipment', 'สินทรัพย์ไม่หมุนเวียน', 'ที่ดิน อาคารและอุปกรณ์', 'Asset', 'งบแสดงฐานะการเงิน', 'ที่ดิน อาคารและอุปกรณ์', 'Investing', .78),
    (r'สินทรัพย์ไม่มีตัวตน|โปรแกรมคอมพิวเตอร์|ลิขสิทธิ์', 'สินทรัพย์ไม่หมุนเวียน', 'สินทรัพย์ไม่มีตัวตน', 'Asset', 'งบแสดงฐานะการเงิน', 'สินทรัพย์ไม่มีตัวตน', 'Investing', .75),
    (r'เจ้าหนี้การค้า|เจ้าหนี้อื่น|accounts payable|trade payable', 'หนี้สินหมุนเวียน', 'เจ้าหนี้การค้าและเจ้าหนี้อื่น', 'Liability', 'งบแสดงฐานะการเงิน', 'เจ้าหนี้การค้าและเจ้าหนี้อื่น', 'Operating', .82),
    (r'ภาษีหัก ณ ที่จ่ายค้างจ่าย|ภาษีค้างจ่าย|ภาษีขายรอนำส่ง|ภาษีเงินได้นิติบุคคลค้างจ่าย', 'หนี้สินหมุนเวียน', 'ภาษีค้างจ่าย', 'Liability', 'งบแสดงฐานะการเงิน', 'ภาษีค้างจ่าย', 'Operating', .78),
    (r'เงินกู้ยืม|เงินกู้|loan|borrow', 'หนี้สิน', 'เงินกู้ยืม', 'Liability', 'งบแสดงฐานะการเงิน', 'เงินกู้ยืม', 'Financing', .78),
    (r'ทุนจดทะเบียน|ทุนที่ออก|ทุนชำระแล้ว|share capital', 'ส่วนของผู้ถือหุ้น', 'ทุน', 'Equity', 'งบแสดงฐานะการเงิน', 'ทุน', 'Financing', .8),
    (r'กำไรสะสม|ขาดทุนสะสม|retained earnings', 'ส่วนของผู้ถือหุ้น', 'กำไรสะสม', 'Equity', 'งบแสดงฐานะการเงิน', 'กำไรสะสม', 'Financing', .85),
    (r'รายได้จากการขาย|รายได้จากการให้บริการ|รายได้ค่าบริการ|รายได้ขาย|sales revenue|service revenue', 'รายได้', 'รายได้จากการขายหรือการให้บริการ', 'Revenue', 'งบกำไรขาดทุน', 'รายได้จากการขายหรือการให้บริการ', 'Operating', .84),
    (r'รายได้อื่น|ดอกเบี้ยรับ|กำไรจากอัตราแลกเปลี่ยน', 'รายได้', 'รายได้อื่น', 'Revenue', 'งบกำไรขาดทุน', 'รายได้อื่น', 'Operating', .72),
    (r'ต้นทุนขาย|ต้นทุนบริการ|ต้นทุนการให้บริการ|cost of sales', 'ค่าใช้จ่าย', 'ต้นทุนขายหรือต้นทุนการให้บริการ', 'Expense', 'งบกำไรขาดทุน', 'ต้นทุนขายหรือต้นทุนการให้บริการ', 'Operating', .82),
    (r'เงินเดือน|ค่าเช่าสำนักงาน|ค่าโทรศัพท์|ค่าสาธารณูปโภค|ค่าใช้จ่ายสำนักงาน|ค่าใช้จ่ายบริหาร|ค่าเสื่อมราคา', 'ค่าใช้จ่าย', 'ค่าใช้จ่ายในการบริหาร', 'Expense', 'งบกำไรขาดทุน', 'ค่าใช้จ่ายในการบริหาร', 'Operating', .65),
    (r'ค่าโฆษณา|ค่านายหน้า|ค่าขนส่งขาย|ค่าใช้จ่ายขาย', 'ค่าใช้จ่าย', 'ค่าใช้จ่ายในการขาย', 'Expense', 'งบกำไรขาดทุน', 'ค่าใช้จ่ายในการขาย', 'Operating', .75),
    (r'ดอกเบี้ยจ่าย|ค่าใช้จ่ายทางการเงิน|finance cost', 'ค่าใช้จ่าย', 'ค่าใช้จ่ายทางการเงิน', 'Expense', 'งบกำไรขาดทุน', 'ค่าใช้จ่ายทางการเงิน', 'Operating', .82),
    (r'ภาษีเงินได้|ภาษีเงินได้นิติบุคคล', 'ค่าใช้จ่าย', 'ภาษีเงินได้', 'Expense', 'งบกำไรขาดทุน', 'ภาษีเงินได้', 'Operating', .8),
]
SUSPICIOUS = re.compile(r'suspense|พักบัญชี|รอตรวจสอบ|บัญชีพัก|memo|memorandum|ภาษี|กรรมการ|ผู้ถือหุ้น|related party|ระหว่างกัน|สะสม|contra', re.I)

def suggest_mapping(tb: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for _, r in tb.iterrows():
        code=str(r.get('Account Code','')).strip(); name=str(r.get('Account Name','')).strip(); text=f'{code} {name}'
        found=None
        for pattern, group, sub, typ, fs, line, cf, conf in RULES:
            if re.search(pattern, text, re.I):
                found=(group,sub,typ,fs,line,cf,conf,pattern); break
        if found:
            group,sub,typ,fs,line,cf,conf,pattern=found
            method='Rule-based Suggestion'; reason=f'ตรงกับกฎคำสำคัญ /{pattern}/'
            status='Pending'
        else:
            group,sub,typ,fs,line,cf,conf='ต้องสอบทาน','ยังไม่จัดประเภท','Unclassified','ยังไม่กำหนด','ยังไม่กำหนด','Pending Review',0.0
            method='Unmapped'; reason='ไม่พบกฎที่ตรงกัน ต้องให้ผู้ใช้จัดประเภท'
            status='Pending'
        if SUSPICIOUS.search(text):
            conf=min(conf,.49); reason += ' | มีคำที่ต้องสอบทานเป็นพิเศษ'; status='Pending'
        rows.append({'Account Code':code,'Account Name':name,'Account Type':typ,'Grouping':group,'Sub Grouping':sub,
                     'Financial Statement':fs,'Financial Statement Line Item':line,'DBD Line Item':'Pending DBD confirmation',
                     'Note Number':'','Cash Flow Classification':cf,'Mapping Method':method,'Confidence':conf,
                     'Reviewer Status':status,'Reviewer':'','Reviewed Date':'','Comment':reason,
                     'Source Row':r.get('_Source_Row','')})
    return pd.DataFrame(rows)
