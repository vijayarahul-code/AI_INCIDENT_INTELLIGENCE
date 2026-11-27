from __future__ import annotations

from typing import Dict, List

from database.db import DBManager


class NotificationService:
    def __init__(self, db_manager: DBManager | None = None):
        self.db = db_manager or DBManager()

    def create_alert(self, incident_id: str | None, message: str, notification_type: str) -> None:
        self.db.add_notification(incident_id, message, notification_type)

    def critical_incident_alert(self, incident_id: str, severity: str) -> None:
        if severity.lower() == "critical":
            self._create_deduplicated_alert(
                incident_id,
                f"Confirmed critical incident alert for {incident_id}",
                "critical",
            )

    def predicted_critical_alert(self, incident_id: str, severity: str) -> None:
        if severity.lower() == "critical":
            self._create_deduplicated_alert(
                incident_id,
                f"Model predicted critical severity for {incident_id}; human review is required",
                "predicted_critical",
            )

    def _create_deduplicated_alert(self, incident_id: str, message: str, notification_type: str) -> None:
        existing = self.db.get_notifications(unread_only=True)
        if any(row["incident_id"] == incident_id and row["type"] == notification_type for row in existing):
            return
        self.create_alert(incident_id, message, notification_type)

    def duplicate_notification(self, source_id: str, candidate_id: str) -> None:
        self.create_alert(source_id, f"Potential duplicate detected between {source_id} and {candidate_id}", "duplicate")

    def status_update_notification(self, incident_id: str, new_status: str) -> None:
        self.create_alert(incident_id, f"Incident {incident_id} updated to status: {new_status}", "status")

    def assigned_team_notification(self, incident_id: str, team: str) -> None:
        self.create_alert(incident_id, f"Incident {incident_id} assigned to {team}", "assignment")

    def resolution_notification(self, incident_id: str, resolution: str) -> None:
        self.create_alert(incident_id, f"Resolution recorded for {incident_id}: {resolution}", "resolution")

    def get_unread(self) -> List[Dict[str, str]]:
        rows = self.db.get_notifications(unread_only=True)
        return [dict(row) for row in rows]
