from database.db import DBManager
from recommendation.solution_engine import recommend_solutions


def test_recommendations_use_resolved_database_rows_and_exclude_source(tmp_path):
    db = DBManager(tmp_path / "recommendations.sqlite")
    db.initialize_database()
    db.insert_incident(
        "REC-SOURCE",
        "Login issue",
        "Login button is not responding after session refresh",
        "Authentication",
        "High",
        "Resolved",
        "Identity",
        "2026-01-01",
        "Source resolution",
    )
    db.insert_incident(
        "REC-HISTORY",
        "Login button failure",
        "Login button stopped responding when the session token expired",
        "Authentication",
        "High",
        "Resolved",
        "Identity",
        "2025-12-01",
        "Refresh the session token and clear the stale authentication cache",
    )
    db.insert_incident(
        "REC-OPEN",
        "Open login issue",
        "Login button is not responding",
        "Authentication",
        "High",
        "Open",
        "Identity",
        "2026-01-02",
        "Not resolved yet",
    )

    recommendations = recommend_solutions(
        "REC-SOURCE",
        "Login button is not responding after session refresh",
        threshold=0.1,
        db_manager=db,
    )

    assert [item["incident_id"] for item in recommendations] == ["REC-HISTORY"]
    assert recommendations[0]["historical_incident_id"] == "REC-HISTORY"
    assert recommendations[0]["source_incident_id"] == "REC-SOURCE"
    assert recommendations[0]["resolution_details"].startswith("Refresh the session")
    assert 0.0 <= recommendations[0]["similarity_score"] <= 1.0