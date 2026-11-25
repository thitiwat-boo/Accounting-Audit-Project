from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from src.config_loader import get_audit_rules
from src.models import EntitySetup


def score_risk_level(score: float, low_max: int = 29, med_max: int = 54, high_max: int = 79) -> str:
    if score <= low_max:
        return "Low"
    if score <= med_max:
        return "Medium"
    if score <= high_max:
        return "High"
    return "Critical"


def build_account_risk_register_and_workpaper(
    adjusted_tb: pd.DataFrame,
    gl_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
    setup: EntitySetup,
    weights: dict[str, int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build explainable Account-Level Risk Register and Audit_Workpaper (Section 7.1 & 7.2)."""
    if adjusted_tb.empty:
        return pd.DataFrame(), pd.DataFrame()

    rules = get_audit_rules()
    w = weights or rules.get("risk_weights", {})
    mat = max(1.0, float(setup.materiality_amount))

    map_lookup = mapping_df.set_index("Account_Code").to_dict(orient="index") if not mapping_df.empty else {}
    gl_stats: dict[str, dict[str, Any]] = {}
    if gl_df is not None and not gl_df.empty:
        p_end = pd.Timestamp(setup.period_end)
        for code, grp in gl_df.groupby("Account_Code"):
            manual_cnt = int(
                (
                    grp["Entry_Type"].str.lower().str.contains("manual|adjust|close|jv", na=False)
                    | grp["Doc_No"].str.upper().str.startswith(("JV", "AJ", "ADJ", "JE"))
                ).sum()
            )
            cutoff_cnt = int(
                (
                    grp["Date"].notna()
                    & (grp["Date"] >= p_end - pd.Timedelta(days=5))
                    & (grp["Date"] <= p_end)
                ).sum()
            )
            no_ref_cnt = int((grp["Reference"].astype(str).str.strip() == "").sum())
            gl_stats[str(code)] = {
                "tx_count": len(grp),
                "manual_cnt": manual_cnt,
                "cutoff_cnt": cutoff_cnt,
                "no_ref_cnt": no_ref_cnt,
                "sample_refs": ", ".join(grp["GL_Ref"].head(3).astype(str).tolist()),
            }

    risk_rows: list[dict[str, Any]] = []
    wp_rows: list[dict[str, Any]] = []

    for idx, r in adjusted_tb.iterrows():
        code = str(r["Account_Code"])
        name = str(r["Account_Name"])
        bal = abs(float(r["Adjusted_Net"]))
        prior = abs(float(r.get("Prior_Balance", 0.0)))
        grp_name = str(r.get("Grouping", ""))
        m = map_lookup.get(code, {})
        gs = gl_stats.get(code, {"tx_count": 0, "manual_cnt": 0, "cutoff_cnt": 0, "no_ref_cnt": 0, "sample_refs": ""})

        factors: list[str] = []
        score = 0.0

        # 1. Materiality ratio
        mat_ratio = bal / mat
        if mat_ratio >= 2.0:
            score += w.get("materiality_ratio", 25)
            factors.append(f"ยอดคงเหลือ >= 2x Materiality ({mat_ratio:.1f}x)")
        elif mat_ratio >= 1.0:
            score += w.get("materiality_ratio", 25) * 0.7
            factors.append(f"ยอดคงเหลือ >= Materiality ({mat_ratio:.1f}x)")
        elif mat_ratio >= 0.5:
            score += w.get("materiality_ratio", 25) * 0.4
            factors.append(f"ยอดคงเหลือ >= 50% Materiality ({mat_ratio:.1f}x)")

        # 2. Period fluctuation
        if prior > 1.0:
            pct_chg = abs(bal - prior) / prior
            if pct_chg >= 0.5:
                score += w.get("period_fluctuation", 15)
                factors.append(f"ผันผวนจากงวดก่อน {pct_chg*100:.0f}%")
            elif pct_chg >= 0.25:
                score += w.get("period_fluctuation", 15) * 0.5
                factors.append(f"เปลี่ยนแปลงจากงวดก่อน {pct_chg*100:.0f}%")

        # 3. Manual journals / Management override
        if gs["manual_cnt"] > 0:
            score += w.get("management_override_or_manual", 15)
            factors.append(f"มี Manual/Adjusting Journal {gs['manual_cnt']} รายการ")

        # 4. Year-end cut-off
        if gs["cutoff_cnt"] > 0:
            score += w.get("year_end_cutoff", 15)
            factors.append(f"มีรายการใกล้วันสิ้นงวด {gs['cutoff_cnt']} รายการ")

        # 5. Related party
        if bool(m.get("Related_Party_Flag", False)):
            score += w.get("related_party", 10)
            factors.append("เกี่ยวข้องกับบุคคล/กิจการที่เกี่ยวข้องกัน")

        # 6. Estimates / Complexity
        is_est = any(k in name.lower() for k in ["ค่าเผื่อ", "ประมาณการ", "ค่าเสื่อม", "ภาษีเงินได้", "allowance", "provision", "depreciation", "lease"])
        if is_est:
            score += w.get("accounting_complexity_or_estimate", 10)
            factors.append("เกี่ยวข้องกับประมาณการทางบัญชี/Judgment")

        # 7. Suspense / Unmapped / Missing GL Ref
        if r.get("Mapping_Status") in ("Unmapped", "Rejected") or "บัญชีพัก" in grp_name or gs["no_ref_cnt"] > 0:
            score += w.get("evidence_gap_or_suspense", 10)
            if "บัญชีพัก" in grp_name or r.get("Mapping_Status") in ("Unmapped", "Rejected"):
                factors.append("บัญชีพักหรือยังไม่ยืนยัน Mapping")
            if gs["no_ref_cnt"] > 0:
                factors.append(f"พบรายการ GL ขาด Reference {gs['no_ref_cnt']} แถว")

        score = min(100.0, round(score, 1))
        level = score_risk_level(score, setup.risk_low_max, setup.risk_medium_max, setup.risk_high_max)

        # Match suggested procedure from audit_cycles
        proc = "Suggested Audit Procedure: สุ่มตรวจเอกสารประกอบรายการ (Vouching) และกระทบยอดคงเหลือ ณ วันสิ้นงวด"
        evidence = "รายละเอียดประกอบยอดบัญชี (Sub-ledger), ใบสำคัญ, เอกสารอนุมัติ"
        assertions = "Existence, Accuracy, Valuation"
        for cyc in rules.get("audit_cycles", []):
            cyc_l = cyc["cycle"].lower()
            if (
                ("เงินสด" in grp_name and "เงินสด" in cyc_l)
                or ("ลูกหนี้" in grp_name and "ลูกหนี้" in cyc_l)
                or ("สินค้า" in grp_name and "สินค้า" in cyc_l)
                or ("อุปกรณ์" in name and "อุปกรณ์" in cyc_l)
                or ("เจ้าหนี้" in grp_name and "เจ้าหนี้" in cyc_l)
                or ("เงินกู้" in grp_name and "เงินกู้" in cyc_l)
                or ("รายได้" in grp_name and "รายได้" in cyc_l)
                or ("ค่าใช้จ่าย" in grp_name and "ค่าใช้จ่าย" in cyc_l)
                or ("ภาษี" in name and "ภาษี" in cyc_l)
                or ("ทุน" in grp_name or "กำไรสะสม" in name) and "ส่วนของเจ้าของ" in cyc_l
            ):
                proc = cyc["procedure"]
                evidence = cyc["evidence"]
                assertions = ", ".join(cyc["assertions"])
                break

        sample_n = max(1, min(25, int(np.ceil(gs["tx_count"] * (0.3 if level in ("High", "Critical") else 0.1))))) if gs["tx_count"] > 0 else 1

        risk_rows.append(
            {
                "Risk_ID": f"RSK-ACC-{idx+1:03d}",
                "Account_Code": code,
                "Account_Name": name,
                "Grouping": grp_name,
                "Population_Amount": round(bal, 2),
                "Materiality_Ratio": round(mat_ratio, 2),
                "Risk_Score": score,
                "Risk_Level": level,
                "Risk_Factors": "; ".join(factors) if factors else "ไม่พบสัญญาณความเสี่ยงเฉพาะเจาะจง",
                "Assertion": assertions,
                "Suggested_Procedure": proc,
            }
        )

        wp_rows.append(
            {
                "WP_Reference": f"WP-{code}",
                "Account_Cycle": f"{code} - {name}",
                "Financial_Statement_Area": grp_name,
                "Assertion": assertions,
                "Risk_Description": "; ".join(factors) if factors else "Normal routine balance",
                "Risk_Rating": level,
                "Materiality_Comparison": f"{mat_ratio:.2f}x Materiality ({'Material' if mat_ratio >= 1.0 else 'Below Materiality'})",
                "Population_Amount": round(bal, 2),
                "Sampling_Method": "Monetary Unit / Risk-Targeted Sampling (Suggested)" if level in ("High", "Critical") else "Haphazard / Analytical Review",
                "Sample_Size_Suggestion": sample_n,
                "Selected_Samples": gs["sample_refs"] or "Account Balance Schedule",
                "Proposed_Audit_Procedure": proc,
                "Evidence_Required": evidence,
                "Evidence_Received": "[รอหลักฐานจากกิจการ]",
                "Exception": "Pending Testing",
                "Management_Response": "",
                "Conclusion": "Open - Pending CPA Review",
                "Prepared_By": "",
                "Reviewed_By": "",
                "Date": str(setup.period_end),
                "Status": "Open",
                "Source_Row_Link": f"Adjusted_TB!A{idx+2}",
            }
        )

    return pd.DataFrame(risk_rows), pd.DataFrame(wp_rows)
