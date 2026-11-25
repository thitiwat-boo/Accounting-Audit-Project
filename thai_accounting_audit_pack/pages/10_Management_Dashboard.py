from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.accounting_rules import compute_adjusted_tb
from src.audit_tests import build_supplementary_audit_sheets, run_revenue_and_expense_review
from src.financial_statements import build_financial_statements
from src.mapping import detect_mapping_conflicts_and_unmapped
from src.notes import build_notes_and_checklist
from src.risk_scoring import build_account_risk_register_and_workpaper
from src.ui_helpers import render_page_review_signoff, render_sidebar_and_header


st.set_page_config(page_title="10 Management Dashboard", page_icon="📈", layout="wide")
setup = render_sidebar_and_header("dashboard", "10. Management, Accounting Close & Audit Readiness Dashboard", "10. 3-View Management Dashboard")
lang = setup.language

tb_df = st.session_state["tb_normalized"]
gl_df = st.session_state["gl_normalized"]
mapping_df = st.session_state["coa_mapping"]

if tb_df.empty:
    st.info("กรุณานำเข้าข้อมูล TB/GL เพื่อแสดงผล Dashboard")
    render_page_review_signoff("dashboard", lang)
    st.stop()

adjusted_tb = compute_adjusted_tb(tb_df, st.session_state["adjustments"], mapping_df)
fs_res = build_financial_statements(adjusted_tb, setup, st.session_state["prior_year_review"], st.session_state["prior_year_mode"])
risk_reg_df, wp_df = build_account_risk_register_and_workpaper(adjusted_tb, gl_df, mapping_df, setup, st.session_state["risk_weights"])
rev_df, exp_df = run_revenue_and_expense_review(adjusted_tb, gl_df, mapping_df, setup)
supp = build_supplementary_audit_sheets(adjusted_tb, gl_df, mapping_df, setup)
unmapped_df, _ = detect_mapping_conflicts_and_unmapped(mapping_df, tb_df)
notes_idx = st.session_state["notes_index"]
if notes_idx.empty:
    notes_idx, _ = build_notes_and_checklist(adjusted_tb, setup)

# Filters
st.subheader("ตัวกรองข้อมูล (Filters)")
f1, f2, f3, f4 = st.columns(4)
grp_opts = ["ทั้งหมด"] + sorted(adjusted_tb["Grouping"].unique().tolist())
sel_grp = f1.selectbox("กลุ่มบัญชี (Grouping)", options=grp_opts)
dept_opts = ["ทั้งหมด"] + (sorted(gl_df["Department"].dropna().unique().tolist()) if not gl_df.empty else [])
sel_dept = f2.selectbox("หน่วยงาน (Department - GL)", options=dept_opts)
risk_opts = ["ทั้งหมด", "Critical", "High", "Medium", "Low"]
sel_risk = f3.selectbox("ระดับความเสี่ยง", options=risk_opts)
if not gl_df.empty and gl_df["Date"].notna().any():
    min_d = gl_df["Date"].min().date()
    max_d = gl_df["Date"].max().date()
    date_rng = f4.date_input("ช่วงวันที่ (GL)", value=(min_d, max_d))
else:
    date_rng = None
    f4.caption("ไม่มีช่วงวันที่ GL")

# Filtered views
filt_atb = adjusted_tb.copy()
if sel_grp != "ทั้งหมด":
    filt_atb = filt_atb[filt_atb["Grouping"] == sel_grp]

filt_gl = gl_df.copy() if not gl_df.empty else pd.DataFrame()
if not filt_gl.empty:
    if sel_dept != "ทั้งหมด":
        filt_gl = filt_gl[filt_gl["Department"] == sel_dept]
    if date_rng and isinstance(date_rng, tuple) and len(date_rng) == 2:
        filt_gl = filt_gl[(filt_gl["Date"].isna()) | ((filt_gl["Date"] >= pd.Timestamp(date_rng[0])) & (filt_gl["Date"] <= pd.Timestamp(date_rng[1])))]

filt_risk = risk_reg_df.copy()
if sel_risk != "ทั้งหมด" and not filt_risk.empty:
    filt_risk = filt_risk[filt_risk["Risk_Level"] == sel_risk]

div = setup.unit_divisor
rec = fs_res["reconciliations"]
rev_tot = float(rec.get("revenue", 0.0))
gp = float(rec.get("gross_profit", 0.0))
ni = float(rec.get("net_income", 0.0))
ebit = float(rec.get("ebit", 0.0))
depr_sum = float(adjusted_tb[adjusted_tb["Account_Name"].str.contains("ค่าเสื่อม|depreciation", case=False, na=False) & (adjusted_tb["Account_Type"] == "Expense")]["Adjusted_FS_Amount"].sum()) / div
ebitda = ebit + depr_sum
cash_bal = float(rec.get("cash_ending", 0.0))
ar_bal = float(adjusted_tb[adjusted_tb["FS_Line_Item"] == "ลูกหนี้การค้าและลูกหนี้อื่น"]["Adjusted_FS_Amount"].sum()) / div
inv_bal = float(adjusted_tb[adjusted_tb["FS_Line_Item"] == "สินค้าคงเหลือ"]["Adjusted_FS_Amount"].sum()) / div
ap_bal = float(adjusted_tb[adjusted_tb["FS_Line_Item"] == "เจ้าหนี้การค้าและเจ้าหนี้อื่น"]["Adjusted_FS_Amount"].sum()) / div
cogs_abs = float(adjusted_tb[adjusted_tb["Grouping"] == "ต้นทุนขายหรือต้นทุนการให้บริการ"]["Adjusted_FS_Amount"].sum()) / div
tot_liab = float(rec.get("total_liabilities", 0.0))
tot_eq = float(rec.get("total_equity", 0.0))

gm_pct = (gp / rev_tot * 100.0) if rev_tot else 0.0
nm_pct = (ni / rev_tot * 100.0) if rev_tot else 0.0
de_ratio = (tot_liab / tot_eq) if tot_eq else 0.0
dso = (ar_bal / rev_tot * 365.0) if rev_tot > 0 else None
dpo = (ap_bal / cogs_abs * 365.0) if cogs_abs > 0 else None
inv_days = (inv_bal / cogs_abs * 365.0) if cogs_abs > 0 else None

view_tabs = st.tabs(["1. Executive Dashboard", "2. Accounting Close Dashboard", "3. Audit Readiness Dashboard"])

# === VIEW 1: EXECUTIVE ===
with view_tabs[0]:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("รายได้รวม", f"{rev_tot:,.2f} {setup.unit_scale}")
    k2.metric("กำไรขั้นต้น", f"{gp:,.2f}", f"GM {gm_pct:.1f}%")
    k3.metric("EBITDA (ประมาณการ)", f"{ebitda:,.2f}", f"EBIT + Depr {depr_sum:,.2f}")
    k4.metric("กำไรสุทธิ", f"{ni:,.2f}", f"NM {nm_pct:.1f}%")
    k5.metric("เงินสดและเทียบเท่า", f"{cash_bal:,.2f}")

    k6, k7, k8, k9, k10 = st.columns(5)
    k6.metric("ลูกหนี้การค้าสุทธิ", f"{ar_bal:,.2f}", f"DSO: {dso:.1f} วัน" if dso is not None else "DSO: N/A")
    k7.metric("เจ้าหนี้การค้าและอื่น", f"{ap_bal:,.2f}", f"DPO: {dpo:.1f} วัน" if dpo is not None else "DPO: N/A")
    k8.metric("สินค้าคงเหลือ", f"{inv_bal:,.2f}", f"DIO: {inv_days:.1f} วัน" if inv_days is not None else "DIO: N/A")
    k9.metric("หนี้สินต่อทุน (D/E)", f"{de_ratio:.2f}x")
    k10.metric("High/Critical Risk", f"{int(risk_reg_df['Risk_Level'].isin(['High', 'Critical']).sum()) if not risk_reg_df.empty else 0}")

    with st.expander("📐 View calculation: สูตรและแหล่งที่มาของ KPI ทุกตัว (100% Traceable)"):
        kpi_trace = pd.DataFrame([
            {"KPI": "รายได้รวม", "Value": rev_tot, "Formula": "SUM(Adjusted_TB!Adjusted_FS_Amount where Grouping='รายได้จากการขายหรือการให้บริการ') / UnitDivisor", "Source": "FS_Income_Statement / D_Revenue"},
            {"KPI": "กำไรขั้นต้น", "Value": gp, "Formula": "Revenue - COGS", "Source": "FS_Income_Statement"},
            {"KPI": "EBITDA", "Value": ebitda, "Formula": "EBIT + Depreciation/Amortization Expense", "Source": "FS_Income_Statement + Adjusted_TB (Depr accounts)"},
            {"KPI": "กำไรสุทธิ", "Value": ni, "Formula": "EBT - Income Tax Expense", "Source": "FS_Income_Statement"},
            {"KPI": "D/E Ratio", "Value": de_ratio, "Formula": "Total Liabilities / Total Equity", "Source": "FS_Balance_Sheet"},
            {"KPI": "DSO / DPO / Inventory Days", "Value": dso or 0.0, "Formula": "(Ending AR / Revenue)*365 | (Ending AP / COGS)*365 | (Ending Inv / COGS)*365", "Source": "D_AR_Trade_Other, D_AP_Trade_Other, D_Inventory (หมายเหตุ: คำนวณจากยอดคงเหลือปลายงวด หากต้องการค่าเฉลี่ยต้องใช้ยอดต้นงวด)"},
        ])
        st.dataframe(kpi_trace, use_container_width=True, hide_index=True)

    c_ch1, c_ch2 = st.columns(2)
    with c_ch1:
        st.subheader("Waterfall: จากรายได้สู่กำไรสุทธิ")
        wf_data = pd.DataFrame([
            {"Step": "รายได้ขาย/บริการ", "Amount": rev_tot, "Measure": "relative"},
            {"Step": "ต้นทุนขาย/บริการ", "Amount": -cogs_abs, "Measure": "relative"},
            {"Step": "กำไรขั้นต้น", "Amount": gp, "Measure": "total"},
            {"Step": "ค่าใช้จ่ายขาย/บริหาร/อื่นๆสุทธิ", "Amount": -(gp - ebit), "Measure": "relative"},
            {"Step": "ต้นทุนทางการเงินและภาษี", "Amount": -(ebit - ni), "Measure": "relative"},
            {"Step": "กำไรสุทธิ", "Amount": ni, "Measure": "total"},
        ])
        fig_wf = go.Figure(go.Waterfall(
            x=wf_data["Step"], y=wf_data["Amount"], measure=wf_data["Measure"],
            texttemplate="%{y:,.0f}",
        ))
        fig_wf.update_layout(height=360, margin=dict(t=20, b=20))
        st.plotly_chart(fig_wf, use_container_width=True)
        with st.expander("ดูข้อมูลต้นทาง & ดาวน์โหลด (Waterfall)"):
            st.dataframe(wf_data, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Download Waterfall CSV", wf_data.to_csv(index=False).encode("utf-8-sig"), "waterfall_data.csv")

    with c_ch2:
        st.subheader("ยอดคงเหลือตามกลุ่มบัญชี (Grouping)")
        grp_sum = filt_atb.groupby("Grouping", as_index=False)["Adjusted_FS_Amount"].sum()
        grp_sum["Amount_Scaled"] = grp_sum["Adjusted_FS_Amount"] / div
        fig_grp = px.bar(grp_sum, x="Amount_Scaled", y="Grouping", orientation="h", text_auto=".2s")
        fig_grp.update_layout(height=360, margin=dict(t=20, b=20))
        st.plotly_chart(fig_grp, use_container_width=True)
        with st.expander("ดูข้อมูลต้นทาง & ดาวน์โหลด (Grouping)"):
            st.dataframe(grp_sum, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Download Grouping CSV", grp_sum.to_csv(index=False).encode("utf-8-sig"), "grouping_summary.csv")

    # Monthly Revenue & Expense from GL
    if not filt_gl.empty and filt_gl["Date"].notna().any():
        st.subheader("รายได้ ค่าใช้จ่าย และกำไรรายเดือน (จาก GL_Normalized)")
        rev_codes = set(adjusted_tb[adjusted_tb["Grouping"].isin(["รายได้จากการขายหรือการให้บริการ", "รายได้อื่น"])]["Account_Code"])
        exp_codes = set(adjusted_tb[adjusted_tb["Account_Type"] == "Expense"]["Account_Code"])
        m_gl = filt_gl.dropna(subset=["Date"]).copy()
        m_gl["Month"] = m_gl["Date"].dt.to_period("M").astype(str)
        m_gl["Rev_Amt"] = m_gl.apply(lambda r: (r["Credit"] - r["Debit"]) / div if r["Account_Code"] in rev_codes else 0.0, axis=1)
        m_gl["Exp_Amt"] = m_gl.apply(lambda r: (r["Debit"] - r["Credit"]) / div if r["Account_Code"] in exp_codes else 0.0, axis=1)
        monthly = m_gl.groupby("Month", as_index=False)[["Rev_Amt", "Exp_Amt"]].sum()
        monthly["Net_Profit"] = monthly["Rev_Amt"] - monthly["Exp_Amt"]

        m1, m2 = st.columns(2)
        with m1:
            fig_m = px.bar(monthly, x="Month", y=["Rev_Amt", "Exp_Amt"], barmode="group", title="รายได้ vs ค่าใช้จ่ายรายเดือน")
            st.plotly_chart(fig_m, use_container_width=True)
        with m2:
            fig_p = px.line(monthly, x="Month", y="Net_Profit", markers=True, title="กำไร (ขาดทุน) รายเดือนตาม GL")
            st.plotly_chart(fig_p, use_container_width=True)
        with st.expander("ดูข้อมูลต้นทาง & ดาวน์โหลด (Monthly Trend)"):
            st.dataframe(monthly, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Download Monthly CSV", monthly.to_csv(index=False).encode("utf-8-sig"), "monthly_trend.csv")

# === VIEW 2: ACCOUNTING CLOSE ===
with view_tabs[1]:
    pending_adj = st.session_state["adjustments"][st.session_state["adjustments"]["Status"].isin(["Draft", "Proposed"])] if not st.session_state["adjustments"].empty else pd.DataFrame()
    pending_notes = notes_idx[notes_idx["Status"].isin(["Requires management input", "Requires supporting schedule"])] if not notes_idx.empty else pd.DataFrame()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ผลต่างสมดุล BS", f"{rec.get('bs_balance_diff', 0.0):,.2f}")
    c2.metric("บัญชี Unmapped", f"{len(unmapped_df)}")
    c3.metric("Adjustments รออนุมัติ", f"{len(pending_adj)}")
    c4.metric("Notes รอข้อมูลฝ่ายบริหาร", f"{len(pending_notes)}")

    if not filt_gl.empty and filt_gl["Date"].notna().any():
        st.subheader("แนวโน้มรายการ Manual Journals รายเดือน")
        man_gl = filt_gl[
            filt_gl["Entry_Type"].str.lower().str.contains("manual|adjust|close|jv", na=False)
            | filt_gl["Doc_No"].str.upper().str.startswith(("JV", "AJ", "JE"))
        ].dropna(subset=["Date"]).copy()
        if not man_gl.empty:
            man_gl["Month"] = man_gl["Date"].dt.to_period("M").astype(str)
            man_m = man_gl.groupby("Month", as_index=False).agg(Count=("Doc_No", "count"), Amount=("Debit", "sum"))
            st.plotly_chart(px.bar(man_m, x="Month", y="Count", text="Amount", title="จำนวนและมูลค่ารายการ Manual Journal รายเดือน"), use_container_width=True)
            with st.expander("ดูรายการ Manual Journals ต้นทาง"):
                st.dataframe(man_gl, use_container_width=True, hide_index=True)
        else:
            st.info("ไม่พบรายการ Manual Journal ใน GL ที่กรอง")

# === VIEW 3: AUDIT READINESS ===
with view_tabs[2]:
    high_risk = filt_risk[filt_risk["Risk_Level"].isin(["High", "Critical"])] if not filt_risk.empty else pd.DataFrame()
    open_wp = wp_df[wp_df["Status"] == "Open"] if not wp_df.empty else pd.DataFrame()
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("บัญชีเสี่ยงสูง (High/Critical)", f"{len(high_risk)}")
    a2.metric("รายการต้องยืนยันยอด (Confirmations)", f"{len(supp['Confirmation_Request_List'])}")
    a3.metric("Workpaper สถานะ Open", f"{len(open_wp)}")
    a4.metric("ประเด็นรายได้/ค่าใช้จ่าย", f"{len(rev_df) + len(exp_df)}")

    if not filt_risk.empty:
        top10 = filt_risk.sort_values("Risk_Score", ascending=False).head(10)
        st.subheader("Top 10 บัญชีที่มีคะแนนความเสี่ยงสูงสุด (Explainable Risk Score)")
        fig_r = px.bar(top10, x="Risk_Score", y="Account_Name", color="Risk_Level", orientation="h",
                       color_discrete_map={"Critical": "#DC2626", "High": "#EA580C", "Medium": "#D97706", "Low": "#16A34A"})
        st.plotly_chart(fig_r, use_container_width=True)
        with st.expander("ดูรายละเอียดต้นทาง & ดาวน์โหลด (Top 10 Risk)"):
            st.dataframe(top10, use_container_width=True, hide_index=True)
            st.download_button("⬇️ Download Top10 Risk CSV", top10.to_csv(index=False).encode("utf-8-sig"), "top10_risk.csv")

render_page_review_signoff("dashboard", lang)
