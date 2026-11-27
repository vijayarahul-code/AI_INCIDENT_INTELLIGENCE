from __future__ import annotations

from typing import Any, Dict

from machine_learning.train_model import load_model_bundle


def predict_severity(description: str) -> Dict[str, Any]:
    if not description or not str(description).strip():
        raise ValueError("Incident description is required for prediction.")

    bundle = load_model_bundle()
    model = bundle["model"]
    vectorizer = bundle["vectorizer"]
    vector = vectorizer.transform([description])
    prediction = model.predict(vector)[0]
    probabilities = model.predict_proba(vector)[0]
    confidence = float(max(probabilities))
    return {
        "prediction": prediction,
        "confidence": confidence,
        "probabilities": {label: float(prob) for label, prob in zip(model.classes_, probabilities)},
    }
