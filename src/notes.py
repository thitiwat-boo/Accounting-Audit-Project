from __future__ import annotations

from typing import Any
import pandas as pd

from src.config_loader import get_disclosure_checklist
from src.models import EntitySetup


def build_notes_and_checklist(
    adjusted_tb: pd.DataFrame,
    setup: EntitySetup,
    existing_notes: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate Disclosure Checklist (Notes_Index) and Draft Notes (Notes_Draft) with mandatory management placeholders."""
    cfg = get_disclosure_checklist()
    notes_cfg = cfg.get("notes", [])
    div = setup.unit_divisor

    existing_map: dict[str, dict[str, Any]] = {}
    if existing_notes is not None and not existing_notes.empty:
        for _, r in existing_notes.iterrows():
            existing_map[str(r["Note_No"])] = r.to_dict()

    index_rows: list[dict[str, Any]] = []
    draft_rows: list[dict[str, Any]] = []

    for n in notes_cfg:
        note_no = str(n["note_no"])
        applicable_fws = n.get("applicable_frameworks", [])
        is_applicable = True
        if applicable_fws:
            if setup.framework == "TFRS for NPAEs" and "TFRS for NPAEs" not in applicable_fws:
                is_applicable = False

        linked_grps = n.get("linked_groupings", [])
        amt = 0.0
        acct_count = 0
        if not adjusted_tb.empty and linked_grps:
            sub = adjusted_tb[adjusted_tb["Grouping"].isin(linked_grps)]
            amt = float(sub["Adjusted_FS_Amount"].sum()) / div
            acct_count = len(sub)

        # Determine Status conservatively (never claim confirmed)
        if not is_applicable:
            status = "Not applicable"
        elif n["category"] == "Core":
            status = "Requires CPA review" if setup.entity_name else "Requires management input"
        elif linked_grps and acct_count == 0:
            status = "Not applicable"
        elif n["category"] in ("Disclosure", "Judgment"):
            status = "Requires management input"
        elif acct_count > 0:
            status = "Requires supporting schedule"
        else:
            status = "Requires management input"

        # Preserve user override if reviewed
        prev = existing_map.get(note_no, {})
        if prev.get("Status") in ("Auto-populated", "Requires CPA review", "Not applicable"):
            status = prev["Status"]

        req_inputs = " | ".join(n.get("required_inputs", []))
        draft_text = n["template_th"].format(
            entity_name=setup.entity_name,
            entity_type=setup.effective_entity_type,
            reg_no=setup.registration_no or "[รอเลขทะเบียนนิติบุคคล]",
            business_type=setup.business_type or "[รอประเภทธุรกิจ]",
            framework=setup.custom_framework_name if setup.framework == "TFRS อื่นที่ผู้ใช้กำหนด" and setup.custom_framework_name else setup.framework,
            currency=setup.currency,
            unit_label=setup.unit_scale,
            period_end=str(setup.period_end),
            amount=f"{amt:,.2f}",
        )
        if prev.get("Management_Input_Notes"):
            mgmt_note = prev["Management_Input_Notes"]
        else:
            mgmt_note = ""

        index_rows.append(
            {
                "Note_No": note_no,
                "Title_TH": n["title_th"],
                "Title_EN": n["title_en"],
                "Category": n["category"],
                "Account_Count": acct_count,
                "TB_Amount": round(amt, 2),
                "Status": status,
                "Required_Inputs": req_inputs,
                "Management_Input_Notes": mgmt_note,
            }
        )
        draft_rows.append(
            {
                "Note_No": note_no,
                "Title_TH": n["title_th"],
                "Status": status,
                "Draft_Text": prev.get("Draft_Text", draft_text),
                "Missing_Evidence_Or_Input": req_inputs,
                "Source_Groupings": ", ".join(linked_grps) if linked_grps else "Entity Setup / Management Representation",
            }
        )

    return pd.DataFrame(index_rows), pd.DataFrame(draft_rows)
