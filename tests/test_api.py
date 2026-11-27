from fastapi.testclient import TestClient

from api.app import create_app
from database.db import DBManager


def test_incident_api_crud_validation_and_processing(tmp_path, monkeypatch):
    db = DBManager(tmp_path / "api.sqlite")
    client = TestClient(create_app(db))
    monkeypatch.setattr(
        "incident_processing.processor.predict_severity",
        lambda _: {
            "prediction": "High",
            "confidence": 0.75,
            "probabilities": {"Critical": 0.1, "High": 0.75, "Medium": 0.1, "Low": 0.05},
        },
    )
    payload = {
        "incident_id": "API-1",
        "incident_title": "Login failure",
        "incident_description": "Users cannot sign in to the portal",
        "category": "Authentication",
        "severity": "High",
        "status": "Open",
        "assigned_team": "Identity",
        "created_date": "2026-01-01",
    }

    created = client.post("/api/incidents", json=payload)
    assert created.status_code == 201
    assert created.json()["incident_id"] == "API-1"
    assert client.post("/api/incidents", json=payload).status_code == 409
    assert client.post("/api/incidents", json={**payload, "severity": "Urgent"}).status_code == 422
    assert client.get("/api/incidents/API-1").status_code == 200
    assert len(client.get("/api/incidents").json()) == 1

    updated = client.put("/api/incidents/API-1", json={"status": "Resolved", "resolution_details": "Reset the session"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "Resolved"
    assert client.post("/api/incidents/API-1/process").json()["success"] is True
    assert client.get("/api/incidents/missing").status_code == 404
    assert client.delete("/api/incidents/API-1").status_code == 204
    assert client.delete("/api/incidents/API-1").status_code == 404


def test_incident_api_rejects_empty_update_for_existing_incident(tmp_path):
    db = DBManager(tmp_path / "api-empty-update.sqlite")
    client = TestClient(create_app(db))
    client.post("/api/incidents", json={
        "incident_id": "API-2",
        "incident_title": "Database latency",
        "incident_description": "Database queries are slow",
        "category": "Database",
        "severity": "Medium",
        "status": "Open",
        "assigned_team": "Data Services",
        "created_date": "2026-01-01",
    })
    assert client.put("/api/incidents/API-2", json={}).status_code == 400