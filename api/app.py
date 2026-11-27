from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from database.db import DBManager
from incident_processing.processor import IncidentProcessor


class IncidentCreate(BaseModel):
    incident_id: str = Field(min_length=1, max_length=100)
    incident_title: str = Field(min_length=1, max_length=300)
    incident_description: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=100)
    severity: str = Field(pattern=r"^(Critical|High|Medium|Low)$")
    status: str = Field(default="Open", pattern=r"^(Open|In Progress|Planned|Resolved)$")
    assigned_team: str = Field(min_length=1, max_length=200)
    created_date: date
    resolution_details: str = ""
    source_type: str = "API"
    is_demo: bool = False


class IncidentUpdate(BaseModel):
    incident_title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    incident_description: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    severity: Optional[str] = Field(default=None, pattern=r"^(Critical|High|Medium|Low)$")
    status: Optional[str] = Field(default=None, pattern=r"^(Open|In Progress|Planned|Resolved|Duplicate)$")
    assigned_team: Optional[str] = Field(default=None, min_length=1, max_length=200)
    created_date: Optional[date] = None
    resolution_details: Optional[str] = None
    planned_resolution_date: Optional[date] = None


def create_app(db_manager: DBManager | None = None) -> FastAPI:
    db = db_manager or DBManager()
    db.initialize_database()
    api = FastAPI(
        title="Incident Intelligence API",
        version="1.0.0",
        description="Optional local API for incident CRUD and processing. Swagger docs are available at /docs.",
    )

    @api.post("/api/incidents", status_code=status.HTTP_201_CREATED)
    def create_incident(payload: IncidentCreate):
        incident_id = payload.incident_id.strip()
        try:
            db.insert_incident(
                incident_id=incident_id,
                incident_title=payload.incident_title.strip(),
                incident_description=payload.incident_description,
                category=payload.category.strip(),
                severity=payload.severity,
                status=payload.status,
                assigned_team=payload.assigned_team.strip(),
                created_date=payload.created_date.isoformat(),
                resolution_details=payload.resolution_details,
                source_type=payload.source_type,
                is_demo=int(payload.is_demo),
            )
            db.add_history(incident_id, "created", "Incident created through REST API")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return dict(db.get_incident(incident_id))

    @api.get("/api/incidents")
    def list_incidents():
        return [dict(row) for row in db.get_incidents()]

    @api.get("/api/incidents/{incident_id}")
    def get_incident(incident_id: str):
        row = db.get_incident(incident_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
        return dict(row)

    @api.put("/api/incidents/{incident_id}")
    def update_incident(incident_id: str, payload: IncidentUpdate):
        if db.get_incident(incident_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one update field is required")
        for field in ("created_date", "planned_resolution_date"):
            if field in updates and updates[field] is not None:
                updates[field] = updates[field].isoformat()
        db.update_incident(incident_id, updates)
        db.add_history(incident_id, "updated", f"Fields updated through REST API: {', '.join(sorted(updates))}")
        return dict(db.get_incident(incident_id))

    @api.delete("/api/incidents/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_incident(incident_id: str):
        if db.get_incident(incident_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
        try:
            db.delete_incident(incident_id)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Incident is referenced by a confirmed duplicate relationship and cannot be deleted.",
            ) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @api.post("/api/incidents/{incident_id}/process")
    def process_incident(incident_id: str):
        try:
            return IncidentProcessor(db).process_incident(incident_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @api.post("/api/process/batch")
    def process_batch(threshold: float = 0.35):
        if not 0.0 <= threshold <= 1.0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="threshold must be between 0 and 1")
        return IncidentProcessor(db).process_all(threshold=threshold)

    return api


app = create_app()
