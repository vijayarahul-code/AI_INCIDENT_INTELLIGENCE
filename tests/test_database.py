from database.db import DBManager


def test_database_insert_and_retrieve():
    db = DBManager("incident_test.db")
    db.initialize_database()

    try:
        db.insert_incident(
            incident_id="TEST-1",
            incident_title="Database test issue",
            incident_description="Database connection is failing during peak requests.",
            category="Database",
            severity="High",
            status="Open",
            assigned_team="Data Services",
            created_date="2024-01-01",
            resolution_details="Applied fix",
            source_type="Test",
            is_demo=1,
        )
        row = db.get_incident("TEST-1")
        assert row is not None
        assert row["incident_title"] == "Database test issue"
        db.update_incident("TEST-1", {"status": "Resolved"})
        updated = db.get_incident("TEST-1")
        assert updated["status"] == "Resolved"
    finally:
        db.delete_incident("TEST-1")
        db.close()


def test_independent_connections_share_same_database_without_thread_state_errors():
    db_a = DBManager("incident_test.db")
    db_b = DBManager("incident_test.db")
    db_a.initialize_database()

    incident_id = "TEST-THREAD-1"
    db_a.insert_incident(
        incident_id=incident_id,
        incident_title="Thread-safe database check",
        incident_description="This verifies independent database connections are safe across separate objects.",
        category="Database",
        severity="Medium",
        status="Open",
        assigned_team="Data Services",
        created_date="2024-01-02",
        resolution_details="Verified thread isolation",
        source_type="Test",
        is_demo=1,
    )

    row = db_b.get_incident(incident_id)
    assert row is not None
    assert row["incident_title"] == "Thread-safe database check"

    db_b.update_incident(incident_id, {"status": "Resolved"})
    updated = db_a.get_incident(incident_id)
    assert updated["status"] == "Resolved"

    db_a.delete_incident(incident_id)
    db_a.close()
    db_b.close()
