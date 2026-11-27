from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.db import DBManager
from machine_learning.train_model import train_severity_model


def initialize_application() -> None:
    db = DBManager()
    db.initialize_database()
    db.ensure_demo_seed_data()
    try:
        train_severity_model()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Model training skipped: {exc}")
    print("Application initialized successfully.")


if __name__ == "__main__":
    initialize_application()
