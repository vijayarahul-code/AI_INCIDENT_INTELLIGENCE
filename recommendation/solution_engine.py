from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd
from database.db import DBManager
from duplicate_detection.similarity import compute_similarity_scores


def get_history_dataframe() -> pd.DataFrame:
    db = DBManager()
    rows = db.get_incidents()
    if not rows:
        return pd.DataFrame(columns=["incident_id", "incident_title", "incident_description", "category", "severity", "status", "assigned_team", "resolution_details"])

    records = [dict(r) for r in rows]
    return pd.DataFrame(records)


def find_similar_historical_incidents(
    new_description: str,
    limit: int = 5,
    threshold: float = 0.35,
    db_manager: DBManager | None = None,
    exclude_incident_id: str | None = None,
) -> List[Dict[str, Any]]:
    db = db_manager or DBManager()
    history = [dict(row) for row in db.get_incidents(filters={"status": "Resolved"})]
    if not history or not new_description.strip():
        return []

    candidates = [
        row for row in history
        if row["incident_description"].strip() and row["incident_id"] != exclude_incident_id
    ]
    texts = [new_description] + [str(row["incident_description"]) for row in candidates]
    matches = compute_similarity_scores(texts, threshold=threshold)

    results: List[Dict[str, Any]] = []
    for left, right, score in matches:
        if left == 0:
            row = candidates[right - 1]
            results.append({
                "incident_id": str(row["incident_id"]),
                "incident_title": str(row["incident_title"]),
                "description": str(row["incident_description"]),
                "category": str(row["category"]),
                "severity": str(row["severity"]),
                "status": str(row["status"]),
                "assigned_team": str(row["assigned_team"]),
                "resolution_details": str(row["resolution_details"] or ""),
                "similarity_score": float(score),
                "source_incident_id": row["incident_id"],
            })
    results = sorted(results, key=lambda item: item["similarity_score"], reverse=True)[:limit]
    return results


def recommend_solutions(
    source_incident_id: str,
    description: str,
    threshold: float = 0.35,
    limit: int = 5,
    db_manager: DBManager | None = None,
) -> List[Dict[str, Any]]:
    candidates = find_similar_historical_incidents(
        description,
        limit=limit,
        threshold=threshold,
        db_manager=db_manager,
        exclude_incident_id=source_incident_id,
    )
    recommendations = []
    for item in candidates:
        item["historical_incident_id"] = item["incident_id"]
        item["source_incident_id"] = source_incident_id
        recommendations.append(item)
    return recommendations
