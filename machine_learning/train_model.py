from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT_DIR / "machine_learning" / "model"
MODEL_DIR.mkdir(exist_ok=True)


def load_training_data() -> pd.DataFrame:
    dataset_path = ROOT_DIR / "dataset" / "incidents.csv"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    df = pd.read_csv(dataset_path)
    required = {"Incident Description", "Severity"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Training dataset missing required columns: {sorted(missing)}")
    return df[["Incident Description", "Severity"]].dropna().copy()


def train_severity_model() -> Dict[str, Any]:
    df = load_training_data()
    df["Incident Description"] = df["Incident Description"].astype(str).str.lower()
    df = df[df["Severity"].isin(["Critical", "High", "Medium", "Low"])].copy()

    if len(df) < 10:
        raise ValueError("Training dataset is too small to build a meaningful severity model.")

    X = df["Incident Description"]
    y = df["Severity"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train_tfidf, y_train)
    predictions = model.predict(X_test_tfidf)

    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, predictions, labels=["Critical", "High", "Medium", "Low"])

    joblib.dump(model, MODEL_DIR / "severity_model.joblib")
    joblib.dump(vectorizer, MODEL_DIR / "severity_vectorizer.joblib")

    return {
        "training_rows": int(len(df)),
        "test_size": int(len(X_test)),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "labels": ["Critical", "High", "Medium", "Low"],
    }


def load_model_bundle() -> Dict[str, Any]:
    model_path = MODEL_DIR / "severity_model.joblib"
    vectorizer_path = MODEL_DIR / "severity_vectorizer.joblib"
    if not model_path.exists() or not vectorizer_path.exists():
        raise FileNotFoundError("Trained model files not found. Run training first.")
    model = joblib.load(model_path)
    vectorizer = joblib.load(vectorizer_path)
    return {"model": model, "vectorizer": vectorizer}
