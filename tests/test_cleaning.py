import pandas as pd
import pytest

from data_processing.cleaning import clean_incident_dataframe, load_incident_file, validate_incident_file


def test_missing_values_detection():
    df = pd.DataFrame([
        {
            "Incident ID": "INC-1",
            "Incident Title": "Login failed",
            "Incident Description": "Users cannot log in",
            "Category": "Authentication",
            "Severity": "High",
            "Status": "Open",
            "Assigned Team": "Identity",
            "Created Date": "2024-01-01",
            "Resolution Details": "",
        }
    ])
    cleaned, stats = clean_incident_dataframe(df)
    assert cleaned.shape[0] == 1
    assert "before" in stats and "after" in stats


def test_validation_detects_missing_columns():
    df = pd.DataFrame({"Incident ID": ["INC-1"]})
    validation = validate_incident_file(df)
    assert validation["missing_columns"]


def test_cleaning_rejects_invalid_and_duplicate_rows_and_preserves_source_text():
    df = pd.DataFrame([
        {"Incident ID": "INC001", "Incident Title": " Login  Button ", "Incident Description": " Login  button is NOT responding. ", "Category": "auth", "Severity": "critical", "Status": "in progress", "Assigned Team": " IAM ", "Created Date": "2026-01-01", "Resolution Details": None},
        {"Incident ID": "INC002", "Incident Title": "Bad severity", "Incident Description": "An invalid severity", "Category": "db", "Severity": "Urgent", "Status": "Open", "Assigned Team": "DB", "Created Date": "2026-01-02", "Resolution Details": ""},
        {"Incident ID": "INC003", "Incident Title": "Bad date", "Incident Description": "An invalid date", "Category": "payment", "Severity": "Low", "Status": "Open", "Assigned Team": "Payments", "Created Date": "not-a-date", "Resolution Details": ""},
        {"Incident ID": "INC004", "Incident Title": "Duplicate one", "Incident Description": "Duplicate one", "Category": "db", "Severity": "Low", "Status": "Open", "Assigned Team": "DB", "Created Date": "2026-01-03", "Resolution Details": ""},
        {"Incident ID": "INC004", "Incident Title": "Duplicate two", "Incident Description": "Duplicate two", "Category": "db", "Severity": "Low", "Status": "Open", "Assigned Team": "DB", "Created Date": "2026-01-04", "Resolution Details": ""},
    ])

    cleaned, stats = clean_incident_dataframe(df)

    assert cleaned["Incident ID"].tolist() == ["INC001"]
    assert cleaned.iloc[0]["Incident Description"] == " Login  button is NOT responding. "
    assert cleaned.iloc[0]["Normalized Incident Description"] == "login button is not responding."
    assert cleaned.iloc[0]["Incident Title"] == "Login Button"
    assert cleaned.iloc[0]["Category"] == "Authentication"
    assert cleaned.iloc[0]["Severity"] == "Critical"
    assert cleaned.iloc[0]["Status"] == "In Progress"
    assert cleaned.iloc[0]["Assigned Team"] == "IAM"
    assert stats["original_rows"] == 5
    assert stats["valid_rows"] == 1
    assert stats["invalid_rows"] == 4
    assert stats["duplicate_ids"] == ["INC004"]
    assert {"Severity", "Created Date"}.issubset(
        {issue for row in stats["rejected_records"] for issue in row["issues"]}
    )


def test_load_incident_file_reads_csv_and_xlsx_and_rejects_unsupported_inputs(tmp_path):
    df = pd.DataFrame([
        {"Incident ID": "INC001", "Incident Title": "Login", "Incident Description": "Cannot log in", "Category": "auth", "Severity": "High", "Status": "Open", "Assigned Team": "IAM", "Created Date": "2026-01-01", "Resolution Details": ""},
    ])
    csv_path = tmp_path / "sample.csv"
    xlsx_path = tmp_path / "sample.xlsx"
    xls_path = tmp_path / "sample.xls"
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    assert len(load_incident_file(csv_path)) == 1
    assert len(load_incident_file(xlsx_path)) == 1
    with pytest.raises(ValueError, match=r"Save the workbook as \.xlsx"):
        load_incident_file(xls_path)
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_incident_file(tmp_path / "sample.json")
