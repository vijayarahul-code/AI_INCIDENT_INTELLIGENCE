from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


REQUIRED_COLUMNS = [
    "Incident ID",
    "Incident Title",
    "Incident Description",
    "Category",
    "Severity",
    "Status",
    "Assigned Team",
    "Created Date",
    "Resolution Details",
]

VALID_SEVERITIES = {"Critical", "High", "Medium", "Low"}
SEVERITY_LOOKUP = {value.lower(): value for value in VALID_SEVERITIES}
STATUS_LOOKUP = {"open": "Open", "in progress": "In Progress", "resolved": "Resolved", "planned": "Planned", "duplicate": "Duplicate"}


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def detect_missing_values(df: pd.DataFrame) -> Dict[str, int]:
    missing = df.apply(
        lambda column: column.map(
            lambda value: pd.isna(value) or (isinstance(value, str) and not value.strip())
        ).sum()
    ).to_dict()
    return {key: int(value) for key, value in missing.items() if value > 0}


def identify_duplicate_records(df: pd.DataFrame) -> List[str]:
    if "Incident ID" not in df.columns:
        return []
    duplicates = df[df.duplicated(subset=["Incident ID"], keep=False)]
    return duplicates["Incident ID"].dropna().astype(str).unique().tolist()


def standardize_category(category: Any) -> str:
    if pd.isna(category):
        return "General"
    value = str(category).strip()
    mapping = {
        "auth": "Authentication",
        "authentication": "Authentication",
        "payment": "Payment",
        "db": "Database",
        "database": "Database",
        "infra": "Infrastructure",
        "infrastructure": "Infrastructure",
        "performance": "Performance",
        "frontend": "Frontend",
        "network": "Network",
    }
    key = value.lower().strip()
    return mapping.get(key, value.title())


def validate_severity(values: List[Any]) -> List[str]:
    invalid = []
    for value in values:
        if pd.isna(value):
            invalid.append("missing")
        elif str(value).strip() not in VALID_SEVERITIES:
            invalid.append(str(value).strip())
    return invalid


def validate_dates(values: List[Any]) -> List[str]:
    invalid = []
    for value in values:
        try:
            if pd.notna(value):
                pd.to_datetime(value)
        except Exception:
            invalid.append(str(value))
    return invalid


def validate_incident_file(df: pd.DataFrame) -> Dict[str, Any]:
    issues: Dict[str, Any] = {"missing_columns": [], "invalid_records": [], "duplicate_ids": []}
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    issues["missing_columns"] = missing_columns

    if not missing_columns:
        issues["duplicate_ids"] = identify_duplicate_records(df)
        invalid_rows = []
        duplicate_ids = set(issues["duplicate_ids"])
        required_values = ["Incident ID", "Incident Title", "Incident Description", "Severity", "Status", "Created Date"]
        for position, (_, row) in enumerate(df.iterrows()):
            row_issues = []
            for column in required_values:
                if pd.isna(row.get(column)) or str(row.get(column)).strip() == "":
                    row_issues.append(column)
            severity = str(row.get("Severity", "")).strip().lower()
            if severity and severity not in SEVERITY_LOOKUP:
                row_issues.append("Severity")
            status = str(row.get("Status", "")).strip().lower()
            if status and status not in STATUS_LOOKUP:
                row_issues.append("Status")
            try:
                if pd.notna(row.get("Created Date")):
                    pd.to_datetime(row.get("Created Date"), errors="raise")
            except Exception:
                row_issues.append("Created Date")
            incident_id = str(row.get("Incident ID", "")).strip()
            if incident_id in duplicate_ids:
                row_issues.append("Duplicate Incident ID")
            if row_issues:
                invalid_rows.append({"row_index": position, "incident_id": incident_id, "issues": sorted(set(row_issues))})
        issues["invalid_records"] = invalid_rows
    return issues


def clean_incident_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    validation = validate_incident_file(df)
    rejected_positions = {item["row_index"] for item in validation["invalid_records"]}
    if validation["missing_columns"]:
        rejected_positions = set(range(len(df)))

    valid_positions = [position for position in range(len(df)) if position not in rejected_positions]
    cleaned = df.iloc[valid_positions].copy()
    if "Incident Title" in cleaned:
        cleaned["Incident Title"] = cleaned["Incident Title"].map(
            lambda value: re.sub(r"\s+", " ", str(value)).strip()
        )
    if "Incident Description" in cleaned:
        cleaned["Normalized Incident Description"] = cleaned["Incident Description"].map(normalize_text)
    if "Category" in cleaned:
        cleaned["Category"] = cleaned["Category"].map(standardize_category)
    if "Severity" in cleaned:
        cleaned["Severity"] = cleaned["Severity"].map(
            lambda value: SEVERITY_LOOKUP[str(value).strip().lower()]
        )
    if "Status" in cleaned:
        cleaned["Status"] = cleaned["Status"].map(
            lambda value: STATUS_LOOKUP[str(value).strip().lower()]
        )
    if "Assigned Team" in cleaned:
        cleaned["Assigned Team"] = cleaned["Assigned Team"].map(
            lambda value: "Unassigned" if pd.isna(value) or not str(value).strip() else re.sub(r"\s+", " ", str(value)).strip()
        )
    if "Resolution Details" in cleaned:
        cleaned["Resolution Details"] = cleaned["Resolution Details"].fillna("")
    if "Created Date" in cleaned:
        cleaned["Created Date"] = pd.to_datetime(cleaned["Created Date"]).dt.strftime("%Y-%m-%d")

    before_stats = {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "missing_values": detect_missing_values(df),
    }
    after_stats = {
        "rows": int(len(cleaned)),
        "columns": int(len(cleaned.columns)),
        "missing_values": detect_missing_values(cleaned),
    }
    return cleaned, {
        "before": before_stats,
        "after": after_stats,
        "original_rows": int(len(df)),
        "columns": int(len(df.columns)),
        "valid_rows": int(len(cleaned)),
        "invalid_rows": int(len(rejected_positions)),
        "duplicate_ids": validation["duplicate_ids"],
        "missing_values": detect_missing_values(df),
        "rejected_records": validation["invalid_records"],
        "missing_columns": validation["missing_columns"],
    }


def load_incident_file(file_path: Any) -> pd.DataFrame:
    file_name = getattr(file_path, "name", str(file_path))
    suffix = Path(file_name).suffix.lower()
    source = BytesIO(file_path.getvalue()) if hasattr(file_path, "getvalue") else file_path
    if suffix == ".csv":
        return pd.read_csv(source)
    if suffix == ".xlsx":
        return pd.read_excel(source, engine="openpyxl")
    if suffix == ".xls":
        raise ValueError("Legacy .xls files are not supported in this installation. Save the workbook as .xlsx.")
    raise ValueError("Unsupported file type. Please upload a .csv or .xlsx file.")
