# Accounting & Audit Workbench — Red Team Build

This is a prototype intended for controlled testing. It is **not** a production-ready financial reporting system and does not certify that financial statements comply with Thai accounting standards or DBD forms.

## Run locally / Codespaces

```bash
python -m pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

## Workflow
1. Set up project metadata.
2. Upload TB/GL Excel; choose sheet and map columns.
3. Review validation results.
4. Review and approve COA Mapping suggestions. Rule-based suggestions are not AI output and are not accounting conclusions.
5. Review draft statements and unresolved accounts.
6. Export the preliminary workbook, formulas and source references.

## Important limitations
- Session State is session-scoped, not durable database storage. Download the metadata state and workbook; raw files are retained only in the active app session.
- DBD Line Item remains `Pending DBD confirmation`; do not use as a filing-ready DBD mapping until checked against the current official form applicable to entity type/framework.
- Formula strings are generated and validated with openpyxl. openpyxl does not calculate formula results; open in Excel or LibreOffice to recalculate and inspect displayed values.
- Prior-year extraction/OCR and confirmed comparative mapping are not implemented. Equity movement and cash flow are explicitly marked Cannot Calculate without required support.
- Adjusting entries are captured for workflow demonstration but are not yet fully integrated into Adjusted_TB calculations.
- Audit procedures are risk indicators only and do not produce an audit opinion or fraud conclusion.
- This prototype is not yet multi-user durable storage, and does not include account authentication, tenant-level access controls, or encrypted database persistence. Do not upload real confidential client data to a public repository or unapproved deployment.
- Additional end-to-end testing with representative PEAK exports, Excel/LibreOffice recalculation, and current DBD/TFRS requirements is required before use on real financial statements.
