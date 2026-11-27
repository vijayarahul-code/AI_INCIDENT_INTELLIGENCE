from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


class DBManager:
    INCIDENT_FIELDS = {
        "incident_title",
        "incident_description",
        "normalized_description",
        "category",
        "severity",
        "status",
        "assigned_team",
        "created_date",
        "resolution_details",
        "source_type",
        "is_demo",
        "predicted_severity",
        "prediction_confidence",
        "planned_resolution_date",
        "duplicate_of",
    }

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else Path(__file__).resolve().parent.parent / "incident_intelligence.db"

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize_database(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT UNIQUE NOT NULL,
                    incident_title TEXT NOT NULL,
                    incident_description TEXT NOT NULL,
                    category TEXT,
                    severity TEXT,
                    status TEXT,
                    assigned_team TEXT,
                    created_date TEXT,
                    resolution_details TEXT,
                    source_type TEXT,
                    is_demo INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS duplicate_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_incident_id TEXT NOT NULL,
                    candidate_incident_id TEXT NOT NULL,
                    similarity_score REAL,
                    decision TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS solution_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_incident_id TEXT NOT NULL,
                    recommendation_incident_id TEXT NOT NULL,
                    similarity_score REAL,
                    recommendation TEXT,
                    status TEXT DEFAULT 'suggested',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT,
                    message TEXT NOT NULL,
                    type TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS duplicate_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    duplicate_incident_id TEXT NOT NULL UNIQUE REFERENCES incidents(incident_id) ON DELETE RESTRICT,
                    original_incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE RESTRICT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    CHECK (duplicate_incident_id != original_incident_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    duration_ms REAL NOT NULL,
                    result_json TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            existing_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(incidents)").fetchall()
            }
            migrations = {
                "normalized_description": "TEXT",
                "predicted_severity": "TEXT",
                "prediction_confidence": "REAL",
                "planned_resolution_date": "TEXT",
                "duplicate_of": "TEXT",
            }
            for column, definition in migrations.items():
                if column not in existing_columns:
                    conn.execute(f"ALTER TABLE incidents ADD COLUMN {column} {definition}")
            conn.commit()

    def ensure_demo_seed_data(self) -> None:
        with self._connect() as conn:
            existing = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            if existing > 0:
                return

        csv_path = Path(__file__).resolve().parent.parent / "dataset" / "incidents.csv"
        if not csv_path.exists():
            return

        import pandas as pd

        df = pd.read_csv(csv_path)
        for _, row in df.iterrows():
            self.insert_incident(
                incident_id=str(row["Incident ID"]),
                incident_title=str(row["Incident Title"]),
                incident_description=str(row["Incident Description"]),
                category=str(row.get("Category", "General")),
                severity=str(row.get("Severity", "Medium")),
                status=str(row.get("Status", "Open")),
                assigned_team=str(row.get("Assigned Team", "Unassigned")),
                created_date=str(row.get("Created Date", "2024-01-01")),
                resolution_details=str(row.get("Resolution Details", "")),
                source_type=str(row.get("Source Type", "CSV")),
                is_demo=int(row.get("Is Demo", 1) or 1),
            )

    def insert_incident(
        self,
        incident_id: str,
        incident_title: str,
        incident_description: str,
        category: str,
        severity: str,
        status: str,
        assigned_team: str,
        created_date: str,
        resolution_details: str = "",
        source_type: str = "Manual",
        is_demo: int = 0,
    ) -> Dict[str, Any]:
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO incidents (
                        incident_id, incident_title, incident_description, category, severity,
                        status, assigned_team, created_date, resolution_details, source_type, is_demo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident_id,
                        incident_title,
                        incident_description,
                        category,
                        severity,
                        status,
                        assigned_team,
                        created_date,
                        resolution_details,
                        source_type,
                        is_demo,
                    ),
                )
                conn.commit()
                return {"id": cursor.lastrowid, "incident_id": incident_id}
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Duplicate incident ID: {incident_id}") from exc

    def get_incident(self, incident_id: str) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()

    def get_all_incidents(self, filters: Optional[Dict[str, Any]] = None) -> List[sqlite3.Row]:
        return self.get_incidents(filters=filters)

    def get_incidents(self, filters: Optional[Dict[str, Any]] = None) -> List[sqlite3.Row]:
        query = "SELECT * FROM incidents"
        params: List[Any] = []
        if filters:
            clauses = []
            for key, value in filters.items():
                if key not in self.INCIDENT_FIELDS and key not in {"incident_id", "created_at"}:
                    raise ValueError(f"Unsupported incident filter: {key}")
                if value is not None and value != "":
                    clauses.append(f"{key} = ?")
                    params.append(value)
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def update_incident(self, incident_id: str, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        invalid_fields = set(updates) - self.INCIDENT_FIELDS
        if invalid_fields:
            raise ValueError(f"Unsupported incident fields: {sorted(invalid_fields)}")
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [incident_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE incidents SET {assignments} WHERE incident_id = ?",
                values,
            )
            conn.commit()

    def delete_incident(self, incident_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM incidents WHERE incident_id = ?", (incident_id,))
            conn.commit()

    def add_history(self, incident_id: str, action: str, details: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO incident_history (incident_id, action, details) VALUES (?, ?, ?)",
                (incident_id, action, details),
            )
            conn.commit()

    def record_duplicate_review(self, source_incident_id: str, candidate_incident_id: str, similarity_score: float, decision: str) -> None:
        self.review_duplicate(source_incident_id, candidate_incident_id, similarity_score, decision)

    def review_duplicate(self, source_incident_id: str, candidate_incident_id: str, similarity_score: float, decision: str) -> None:
        if decision not in {"duplicate", "not_duplicate"}:
            raise ValueError("Duplicate review decision must be 'duplicate' or 'not_duplicate'.")
        if source_incident_id == candidate_incident_id:
            raise ValueError("An incident cannot be marked as a duplicate of itself.")
        with self._connect() as conn:
            source = conn.execute("SELECT incident_id FROM incidents WHERE incident_id = ?", (source_incident_id,)).fetchone()
            candidate = conn.execute("SELECT incident_id FROM incidents WHERE incident_id = ?", (candidate_incident_id,)).fetchone()
            if source is None or candidate is None:
                raise ValueError("Both incidents must exist before a duplicate review is recorded.")
            conn.execute(
                "INSERT INTO duplicate_reviews (source_incident_id, candidate_incident_id, similarity_score, decision) VALUES (?, ?, ?, ?)",
                (source_incident_id, candidate_incident_id, similarity_score, decision),
            )
            conn.execute(
                "INSERT INTO incident_history (incident_id, action, details) VALUES (?, ?, ?)",
                (source_incident_id, "duplicate_review", f"{decision}: candidate {candidate_incident_id} (similarity {similarity_score:.4f})"),
            )
            if decision == "duplicate":
                conn.execute(
                    "INSERT INTO duplicate_relationships (duplicate_incident_id, original_incident_id) VALUES (?, ?) "
                    "ON CONFLICT(duplicate_incident_id) DO UPDATE SET original_incident_id = excluded.original_incident_id",
                    (candidate_incident_id, source_incident_id),
                )
                conn.execute(
                    "UPDATE incidents SET status = 'Duplicate', duplicate_of = ? WHERE incident_id = ?",
                    (source_incident_id, candidate_incident_id),
                )
                conn.execute(
                    "INSERT INTO incident_history (incident_id, action, details) VALUES (?, ?, ?)",
                    (candidate_incident_id, "marked_duplicate", f"Confirmed duplicate of {source_incident_id}"),
                )
            conn.commit()

    def get_duplicate_reviews(self, limit: int = 100) -> List[sqlite3.Row]:
        query = """
            SELECT dr.*, source.incident_title AS source_title, candidate.incident_title AS candidate_title
            FROM duplicate_reviews dr
            LEFT JOIN incidents source ON source.incident_id = dr.source_incident_id
            LEFT JOIN incidents candidate ON candidate.incident_id = dr.candidate_incident_id
            ORDER BY dr.created_at DESC, dr.id DESC LIMIT ?
        """
        with self._connect() as conn:
            return conn.execute(query, (limit,)).fetchall()

    def get_incident_history(self, incident_id: str) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM incident_history WHERE incident_id = ? ORDER BY created_at DESC, id DESC",
                (incident_id,),
            ).fetchall()

    def save_processing_result(self, incident_id: str, success: bool, duration_ms: float, result: Dict[str, Any], error: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO processing_results (incident_id, success, duration_ms, result_json, error) VALUES (?, ?, ?, ?, ?)",
                (incident_id, int(success), duration_ms, json.dumps(result, ensure_ascii=True), error),
            )

    def get_processing_results(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM processing_results ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["result"] = json.loads(item.pop("result_json"))
            results.append(item)
        return results

    def mark_notification_read(self, notification_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))

    def record_solution(self, source_incident_id: str, recommendation_incident_id: str, similarity_score: float, recommendation: str, status: str = "suggested") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO solution_records (source_incident_id, recommendation_incident_id, similarity_score, recommendation, status) VALUES (?, ?, ?, ?, ?)",
                (source_incident_id, recommendation_incident_id, similarity_score, recommendation, status),
            )
            conn.commit()

    def add_notification(self, incident_id: str | None, message: str, notification_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO notifications (incident_id, message, type) VALUES (?, ?, ?)",
                (incident_id, message, notification_type),
            )
            conn.commit()

    def get_notifications(self, unread_only: bool = False) -> List[sqlite3.Row]:
        query = "SELECT * FROM notifications"
        params: List[Any] = []
        if unread_only:
            query += " WHERE is_read = 0"
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def search_incidents(self, term: str) -> List[sqlite3.Row]:
        wildcard = f"%{term}%"
        query = """
            SELECT * FROM incidents
            WHERE incident_title LIKE ? OR incident_description LIKE ? OR category LIKE ? OR assigned_team LIKE ?
            ORDER BY created_at DESC
        """
        with self._connect() as conn:
            return conn.execute(query, (wildcard, wildcard, wildcard, wildcard)).fetchall()

    def get_similar_incidents(self, source_incident_id: str, category: Optional[str] = None, limit: int = 5) -> List[sqlite3.Row]:
        if category:
            query = "SELECT * FROM incidents WHERE incident_id != ? AND category = ? ORDER BY created_at DESC LIMIT ?"
            params: List[Any] = [source_incident_id, category, limit]
        else:
            query = "SELECT * FROM incidents WHERE incident_id != ? ORDER BY created_at DESC LIMIT ?"
            params = [source_incident_id, limit]
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def get_solution_recommendations(self, source_incident_id: str, limit: int = 5) -> List[sqlite3.Row]:
        query = """
            SELECT sr.*, i.incident_title, i.category, i.assigned_team, i.status
            FROM solution_records sr
            LEFT JOIN incidents i ON i.incident_id = sr.recommendation_incident_id
            WHERE sr.source_incident_id = ?
            ORDER BY sr.similarity_score DESC
            LIMIT ?
        """
        with self._connect() as conn:
            return conn.execute(query, (source_incident_id, limit)).fetchall()

    def get_summary(self) -> Dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            open_count = conn.execute("SELECT COUNT(*) FROM incidents WHERE status = 'Open'").fetchone()[0]
            resolved_count = conn.execute("SELECT COUNT(*) FROM incidents WHERE status = 'Resolved'").fetchone()[0]
            critical_count = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity = 'Critical'").fetchone()[0]
            duplicate_count = conn.execute("SELECT COUNT(*) FROM duplicate_reviews WHERE decision = 'duplicate'").fetchone()[0]
            return {
                "total_incidents": total,
                "open_incidents": open_count,
                "resolved_incidents": resolved_count,
                "critical_incidents": critical_count,
                "potential_duplicates": duplicate_count,
            }

    def close(self) -> None:
        return None
