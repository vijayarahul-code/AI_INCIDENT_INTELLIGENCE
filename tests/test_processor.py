from database.db import DBManager
from incident_processing.processor import IncidentProcessor


def test_single_incident_processing_compares_against_database_context(tmp_path, monkeypatch):
    db = DBManager(tmp_path / "processor.sqlite")
    db.initialize_database()
    rows = [
        ("PROC-1", "Login button failure", "The login button does not respond after session refresh"),
        ("PROC-2", "Login control unresponsive", "Login button stopped responding after a session refresh"),
        ("PROC-3", "Payment outage", "Payment gateway is unavailable during checkout"),
    ]
    for incident_id, title, description in rows:
        db.insert_incident(incident_id, title, description, "Authentication", "High", "Open", "Support", "2026-01-01")

    monkeypatch.setattr(
        "incident_processing.processor.predict_severity",
        lambda _: {"prediction": "High", "confidence": 0.8, "probabilities": {"High": 0.8}},
    )
    result = IncidentProcessor(db).process_incident("PROC-1", threshold=0.25)

    assert result["success"] is True
    assert any(item["incident_id"] == "PROC-2" for item in result["duplicate_candidates"])
    assert all(item["incident_id"] != "PROC-3" for item in result["duplicate_candidates"])

