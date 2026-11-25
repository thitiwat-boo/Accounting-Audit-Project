# ระบบจัดเตรียมงบการเงิน กระดาษทำการสอบบัญชี และ Management Dashboard จาก TB/GL (Streamlit)

แอปพลิเคชัน **Streamlit** สำหรับนำเข้าไฟล์ Excel (`.xlsx`) ของ Trial Balance (TB), General Ledger (GL) และงบการเงินปีก่อน (`.xlsx` / `.pdf`) เพื่อช่วยผู้ทำบัญชีและผู้สอบบัญชีจัดเตรียมข้อมูล ร่างงบการเงิน หมายเหตุประกอบงบการเงิน กระดาษทำการสอบบัญชี วิเคราะห์ผู้บริหาร และส่งออกเป็น Excel Pack ที่มีสูตรคำนวณจริงตรวจสอบย้อนกลับได้ระดับเซลล์

> ⚠️ **คำเตือนด้านวิชาชีพและความปลอดภัย**
> - เอกสารและตัวเลขทั้งหมดจากระบบนี้เป็น **ฉบับร่างเพื่อการสอบทาน (`Draft for Accountant & CPA Review`)** เท่านั้น
> - ห้ามอ้างว่าเอกสารที่สร้างขึ้นเป็นงบการเงินที่ผ่านการตรวจสอบแล้ว หรือรายงานผู้สอบบัญชีที่ลงนามแล้ว
> - ระบบไม่ส่งข้อมูล TB, GL, งบปีก่อน หรือข้อมูลส่วนบุคคลไปยัง External AI/API ใดๆ

---

## โครงสร้างโครงการ

```text
├── .streamlit/config.toml
├── app.py
├── requirements.txt
├── runtime.txt
├── README.md
├── config/
│   ├── account_mapping_template.xlsx
│   ├── audit_rules.yaml
│   ├── disclosure_checklist.yaml
│   ├── grouping_master.yaml
│   ├── presentation_rules.yaml
│   └── reference_register.yaml
├── sample_data/
│   ├── sample_tb.xlsx
│   ├── sample_gl.xlsx
│   ├── sample_prior_year_fs.xlsx
│   └── sample_prior_year_fs.pdf
├── pages/
│   ├── 00_Entity_and_Framework_Setup.py
│   ├── 01_นำเข้าข้อมูล.py
│   ├── 02_Prior_Year_FS_Import.py
│   ├── 03_ตรวจสอบข้อมูล.py
│   ├── 04_ผังบัญชีและ_Mapping.py
│   ├── 05_Adjusting_Entries.py
│   ├── 06_Financial_Statements.py
│   ├── 07_Notes_to_FS.py
│   ├── 08_Audit_Workpaper.py
│   ├── 09_Auditor_Report_Draft.py
│   ├── 10_Management_Dashboard.py
│   ├── 11_Reconciliation_and_Signoff.py
│   └── 12_Export.py
├── src/
│   ├── accounting_rules.py
│   ├── audit_tests.py
│   ├── auditor_report.py
│   ├── cashflow.py
│   ├── config_loader.py
│   ├── exporters.py
│   ├── financial_statements.py
│   ├── loaders.py
│   ├── mapping.py
│   ├── models.py
│   ├── notes.py
│   ├── prior_year.py
│   ├── provenance.py
│   ├── risk_scoring.py
│   ├── ui_helpers.py
│   └── validators.py
└── tests/
```

---

## แหล่งอ้างอิงทางการที่ใช้ในการออกแบบ (Reference Register)

- **มาตรฐานการรายงานทางการเงิน (TFAC):** https://acpro-std.tfac.or.th/standard/1/
- **TFRS for NPAEs (ปรับปรุง 2565):** https://acpro-std.tfac.or.th/uploads/files/TFRS%20for%20NPAEs.pdf
- **คู่มืออธิบายมาตรฐานการรายงานทางการเงิน (TFAC):** https://acpro-std.tfac.or.th/standard/22
- **มาตรฐานการสอบบัญชี (TSA):** https://acpro-std.tfac.or.th/standard/3/
- **TSA 700 (ปรับปรุง) การแสดงความเห็นและการรายงานต่องบการเงิน (2563):** https://acpro-std.tfac.or.th/uploads/files/TSA/2563_TSA700(Revised).pdf
- **กรมพัฒนาธุรกิจการค้า (DBD):** https://www.dbd.go.th/
- **หน้างานงบการเงินและแบบรายการย่อ พ.ศ. 2566 (DBD):** https://www.dbd.go.th/download-form/10
- **ตัวอย่างโครงสร้างงบการเงินบริษัทจำกัด (DBD แบบ 2):** https://www.dbd.go.th/storage/law/4941272b-c21b-4d78-b1ca-3e63f83252e7.pdf
- **แบบรายการย่อ/งบฐานะการเงิน (DBD):** https://www.dbd.go.th/storage/law/0e0dfc4d-00fe-4541-a97f-6dbe9eeee7f4.pdf
- **DBD e-Filing Portal:** https://efilingfn.dbd.go.th/EfilingRemoteWeb65/memberapply/login.xhtml *(ระบบนี้ไม่ login/ส่งข้อมูลเข้า DBD อัตโนมัติ)*

---

## วิธีติดตั้งและใช้งานบนเครื่อง (Local)

```bash
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
pytest -v
streamlit run app.py
```

---

## วิธี Deploy บน Streamlit Community Cloud

1. Push โฟลเดอร์โครงการขึ้น GitHub Repository (ตรวจให้มี `app.py`, `requirements.txt`, `runtime.txt`, `.streamlit/config.toml`)
2. ไปที่ [share.streamlit.io](https://share.streamlit.io) เลือก Repository และตั้ง Main file path เป็น `app.py`
3. แอปประมวลผลใน `st.session_state` เท่านั้น ไม่มี local path ที่ hard-code และไม่เก็บข้อมูลผู้ใช้ถาวรบน filesystem
4. ผู้ใช้สามารถกด **Config JSON** ในแถบด้านข้างเพื่อบันทึก/กู้คืนการตั้งค่า COA Mapping และสถานะสอบทานข้าม Session ได้
5. หากต้องการใช้ Secret ในอนาคตให้ตั้งค่าผ่าน Streamlit Cloud Secrets (`st.secrets`) เท่านั้น ห้ามใส่ในโค้ด
