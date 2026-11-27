from __future__ import annotations

import re
import time
from typing import Any, Dict, Iterable, List

from automation.notifications import NotificationService
from data_processing.cleaning import normalize_text
from database.db import DBManager
from duplicate_detection.similarity import SIMILARITY_STOP_WORDS, find_potential_duplicates
from duplicate_detection.trie import Trie
from machine_learning.predict import predict_severity
from recommendation.solution_engine import recommend_solutions


class IncidentProcessor:
    def __init__(self, db_manager: DBManager | None = None):
        self.db = db_manager or DBManager()
        self.notifications = NotificationService(self.db)

    def process_all(self, threshold: float = 0.35) -> Dict[str, Any]:
        records = [dict(row) for row in self.db.get_incidents()]
        return self.process_records(records, threshold=threshold)

    def process_incident(self, incident_id: str, threshold: float = 0.35) -> Dict[str, Any]:
        record = self.db.get_incident(incident_id)
        if record is None:
            raise ValueError(f"Incident not found: {incident_id}")
        records = [dict(row) for row in self.db.get_incidents()]
        result = self.process_records(records, threshold=threshold, only_incident_id=incident_id)
        return result["results"][0]

    def process_records(
        self,
        records: Iterable[Dict[str, Any]],
        threshold: float = 0.35,
        only_incident_id: str | None = None,
    ) -> Dict[str, Any]:
        batch_started = time.perf_counter()
        records = list(records)
        # Build the comparison index from the complete incident set. A single
        # incident run limits processing to that row, but must still compare it
        # with every other incident in the database.
        trie = Trie()
        record_by_id = {str(row.get("incident_id", "")): row for row in records}
        target_ids = [
            incident_id for incident_id in record_by_id
            if only_incident_id is None or incident_id == only_incident_id
        ]
        if only_incident_id is not None and only_incident_id not in record_by_id:
            raise ValueError(f"Incident not found: {only_incident_id}")
        normalized_by_id = {}
        for incident_id, row in record_by_id.items():
            description = str(row.get("incident_description") or "")
            normalized = normalize_text(description)
            normalized_by_id[incident_id] = normalized
            for token in re.findall(r"[a-z0-9]+", normalized):
                if len(token) > 2 and token not in SIMILARITY_STOP_WORDS:
                    trie.insert(token, incident_id)

        results = []
        unique_duplicate_pairs = set()
        confirmed_critical = 0
        predicted_critical = 0
        for incident_id in target_ids:
            row = record_by_id[incident_id]
            result = self._process_one(
                incident_id,
                row,
                record_by_id,
                normalized_by_id,
                trie,
                threshold,
            )
            results.append(result)
            unique_duplicate_pairs.update(
                tuple(sorted((incident_id, candidate["incident_id"])))
                for candidate in result.get("duplicate_candidates", [])
            )
            if result.get("success") and str(row.get("severity", "")).lower() == "critical":
                confirmed_critical += 1
            if result.get("success") and result.get("predicted_severity", "").lower() == "critical":
                predicted_critical += 1

        elapsed_ms = (time.perf_counter() - batch_started) * 1000
        successful = sum(bool(result["success"]) for result in results)
        return {
            "total_records_received": len(target_ids),
            "successfully_processed": successful,
            "duplicate_candidates_found": len(unique_duplicate_pairs),
            "critical_incidents_identified": len({
                result["incident_id"] for result in results
                if result.get("success") and (
                    result.get("confirmed_severity", "").lower() == "critical"
                    or result.get("predicted_severity", "").lower() == "critical"
                )
            }),
            "confirmed_critical_incidents": confirmed_critical,
            "predicted_critical_incidents": predicted_critical,
            "failed_records": len(records) - successful,
            "processing_time_ms": round(elapsed_ms, 2),
            "results": results,
        }

    def _process_one(
        self,
        incident_id: str,
        row: Dict[str, Any],
        records: Dict[str, Dict[str, Any]],
        normalized_by_id: Dict[str, str],
        trie: Trie,
        threshold: float,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        result: Dict[str, Any] = {"incident_id": incident_id, "success": False}
        try:
            if not incident_id or not str(row.get("incident_title") or "").strip():
                raise ValueError("Incident ID and title are required.")
            normalized_description = normalized_by_id[incident_id]
            if not normalized_description:
                raise ValueError("Incident description is required.")

            matching_ids = set()
            keywords = sorted({
                token for token in re.findall(r"[a-z0-9]+", normalized_description)
                if len(token) > 2 and token not in SIMILARITY_STOP_WORDS
            })
            for keyword in keywords:
                matching_ids.update(trie.search(keyword))
            matching_ids.discard(incident_id)

            candidates = [
                candidate_id for candidate_id in matching_ids
                if candidate_id in records and normalized_by_id.get(candidate_id)
            ]
            similarities = []
            if candidates:
                texts = [normalized_description] + [normalized_by_id[candidate_id] for candidate_id in candidates]
                similarities = find_potential_duplicates(texts, threshold=threshold)
            duplicate_candidates = []
            for left, right, score in similarities:
                if left != 0:
                    continue
                candidate_id = candidates[right - 1]
                candidate = records[candidate_id]
                duplicate_candidates.append({
                    "incident_id": candidate_id,
                    "incident_title": candidate.get("incident_title", ""),
                    "description": candidate.get("incident_description", ""),
                    "similarity_score": round(score, 4),
                    "similarity_percent": round(score * 100, 1),
                })

            prediction = predict_severity(normalized_description)
            recommendations = recommend_solutions(
                incident_id,
                normalized_description,
                threshold=threshold,
                db_manager=self.db,
            )
            self.db.update_incident(incident_id, {
                "normalized_description": normalized_description,
                "predicted_severity": prediction["prediction"],
                "prediction_confidence": prediction["confidence"],
            })
            self.db.add_history(incident_id, "processed", "Incident processed by the intelligence engine")
            self.notifications.critical_incident_alert(incident_id, str(row.get("severity", "")))
            self.notifications.predicted_critical_alert(incident_id, prediction["prediction"])

            result.update({
                "success": True,
                "keywords": keywords,
                "matching_incident_ids": sorted(matching_ids),
                "duplicate_candidates": duplicate_candidates,
                "confirmed_severity": row.get("severity", ""),
                "predicted_severity": prediction["prediction"],
                "prediction_confidence": prediction["confidence"],
                "severity_probabilities": prediction["probabilities"],
                "historical_recommendations": recommendations,
            })
            self.db.save_processing_result(incident_id, True, (time.perf_counter() - started) * 1000, result)
        except Exception as exc:
            result["error"] = str(exc)
            self.db.save_processing_result(
                incident_id,
                False,
                (time.perf_counter() - started) * 1000,
                result,
                error=str(exc),
            )
        return result
