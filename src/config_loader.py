from __future__ import annotations

from pathlib import Path
from typing import Any
import pandas as pd
import yaml


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def load_yaml_config(filename: str) -> dict[str, Any]:
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_grouping_master() -> dict[str, Any]:
    return load_yaml_config("grouping_master.yaml")


def get_presentation_rules() -> dict[str, Any]:
    return load_yaml_config("presentation_rules.yaml")


def get_disclosure_checklist() -> dict[str, Any]:
    return load_yaml_config("disclosure_checklist.yaml")


def get_audit_rules() -> dict[str, Any]:
    return load_yaml_config("audit_rules.yaml")


def get_reference_register() -> dict[str, Any]:
    return load_yaml_config("reference_register.yaml")


def get_grouping_master_df() -> pd.DataFrame:
    data = get_grouping_master()
    rows = []
    for idx, item in enumerate(data.get("hierarchy", []), start=1):
        rows.append(
            {
                "Rule_ID": f"GRP-{idx:03d}",
                "Version": data.get("version", "1.0.0"),
                "Account_Type": item["account_type"],
                "FS_Sign": item["fs_sign"],
                "Normal_Balance": item["normal_balance"],
                "Grouping": item["grouping"],
                "Sub_Grouping": item["sub_grouping"],
                "FS_Line_Item": item["fs_line_item"],
                "FS_Line_Item_EN": item.get("fs_line_item_en", ""),
                "Disclosure_Lines": " | ".join(item.get("disclosure_lines", [])),
                "Financial_Statement": item["statement"],
                "Detail_Sheet": item["detail_sheet"],
                "Note_No": item["note_no"],
                "Cash_Flow_Class": item["cash_flow_class"],
                "DBD_Line_Item": item["dbd_line_item"],
                "TFAC_Reference": item["tfac_ref"],
                "Keywords": ", ".join(item.get("keywords", [])),
                "Code_Prefixes": ", ".join(item.get("code_prefixes", [])),
            }
        )
    return pd.DataFrame(rows)


def get_presentation_rules_df() -> pd.DataFrame:
    data = get_presentation_rules()
    rows = []
    for r in data.get("rules", []):
        for order, item in enumerate(r.get("required_line_items", []), start=1):
            rows.append(
                {
                    "Framework": r["framework"],
                    "Entity_Type": r["entity_type"],
                    "Effective_Date": r["effective_date"],
                    "Statement_Name": r["statement_name"],
                    "Required_Line_Item": item,
                    "Optional_Line_Item": "",
                    "Display_Order": order,
                    "Current_Non_Current_Rule": r["current_non_current_rule"],
                    "Offset_Rule": r["offset_rule"],
                    "Comparative_Requirement": r["comparative_requirement"],
                    "DBD_Reference": r["dbd_reference"],
                    "TFAC_Reference": r["tfac_reference"],
                }
            )
        for order, item in enumerate(r.get("optional_line_items", []), start=101):
            rows.append(
                {
                    "Framework": r["framework"],
                    "Entity_Type": r["entity_type"],
                    "Effective_Date": r["effective_date"],
                    "Statement_Name": r["statement_name"],
                    "Required_Line_Item": "",
                    "Optional_Line_Item": item,
                    "Display_Order": order,
                    "Current_Non_Current_Rule": r["current_non_current_rule"],
                    "Offset_Rule": r["offset_rule"],
                    "Comparative_Requirement": r["comparative_requirement"],
                    "DBD_Reference": r["dbd_reference"],
                    "TFAC_Reference": r["tfac_reference"],
                }
            )
    return pd.DataFrame(rows)
