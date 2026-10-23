# Accounting, Financial Statements, Audit Workpaper & Dashboard

## ขอบเขต
แอปต้นแบบ Streamlit สำหรับนำเข้า TB/GL, ตรวจสอบคุณภาพข้อมูล, เสนอ COA mapping, สร้างงบฉบับร่างจาก mapping ที่ผู้ใช้อนุมัติ, checklist หมายเหตุ, risk register และ Excel pack

**ไม่ใช่ระบบที่รับรองว่าใช้งานได้ 100% กับทุกผังบัญชี/ทุกมาตรฐาน** ต้องทดสอบกับข้อมูลจริงและให้ผู้ทำบัญชี/ผู้บริหาร/CPA สอบทานก่อนใช้งานจริง

## ติดตั้ง (Windows PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## ติดตั้ง (macOS/Linux)
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## Template
ไฟล์ `templates/TB_GL_Template.xlsx` มี Sheet `TB_Template` และ `GL_Template` พร้อมตัวอย่างข้อมูลสมมติ ไม่ใช่ข้อมูลจริง

## โครงสร้าง
- `app.py`: UI หลัก
- `pages/`: หน้าโมดูล
- `src/`: loaders, validation, mapping, financial statements, audit risk, export
- `config/`: disclosure checklist และ audit rules
- `tests/`: unit tests

## ความปลอดภัยและการเก็บข้อมูล
แอปประมวลผลไฟล์ใน session และไม่มีฐานข้อมูลถาวรในรุ่นนี้ ข้อมูลอาจหายเมื่อ session หรือ instance reset ควรดาวน์โหลดผลลัพธ์ทันที ไม่ส่งข้อมูลไปยัง external AI/API

## ข้อจำกัดสำคัญ
- mapping keyword เป็นเพียงข้อเสนอ; ต้องตรวจสอบ `Reviewer Status = Approved`
- งบที่สร้างเป็น Draft เท่านั้น
- cash flow, tax, comparative figures, consolidation, related-party disclosure และ note disclosures ต้องใช้รายละเอียดสนับสนุนและการยืนยันเพิ่มเติม
- ไม่สร้าง audit opinion อัตโนมัติ
- ตัวอย่าง PDF ที่แนบเป็นงบของบริษัทมหาชนและมีทั้งงบรวม/เฉพาะกิจการ ใช้อ้างอิงรูปแบบเท่านั้น ไม่ใช่ mapping ที่เหมาะกับทุกนิติบุคคล
- รายการย่อ DBD ต้องตรวจสอบกับประกาศฉบับปัจจุบันตามประเภทนิติบุคคลก่อนใช้ยื่นจริง

## Reference register (verify current version before professional use)
- TFAC standards: https://acpro-std.tfac.or.th/standard/1/
- TFRS for NPAEs: https://acpro-std.tfac.or.th/uploads/files/TFRS%20for%20NPAEs.pdf
- TFAC auditing standards: https://acpro-std.tfac.or.th/standard/3/
- DBD financial statements: https://www.dbd.go.th/download-form/10
- DBD e-Filing: https://efilingfn.dbd.go.th/EfilingRemoteWeb65/memberapply/login.xhtml

## Tests
```bash
pytest -q
```
