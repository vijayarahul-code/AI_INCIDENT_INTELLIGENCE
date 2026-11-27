# AI-Powered Incident Intelligence and Automation System

A local-first incident management demo built with Python, Pandas, SQLite, scikit-learn, FastAPI, and Streamlit. It cleans incident CSV/XLSX files, stores incidents, compares descriptions, predicts severity for human review, recommends resolutions from resolved incidents, records alerts, and supports manual duplicate and planned-work review.

## Current functionality

- CSV and `.xlsx` upload with required-field validation, normalization, rejected-row reporting, and duplicate-ID checks.
- SQLite persistence for incidents, processing results, duplicate decisions, incident history, recommendations, and notifications.
- Trie keyword indexing plus TF-IDF/token similarity to surface candidate duplicates for human review.
- Per-incident and batch processing from the dashboard, with stored severity predictions and local alerts.
- Recommendations based on similar resolved incidents already in SQLite.
- Planned incidents with expected resolution dates; a user must verify completion before closing one.
- Optional REST API and optional Jira connection test.

## Important project limits

- The supplied sample data is synthetic and contains only 24 incidents. The severity model is for demonstration and requires human review; it is not reliable enough for operational decisions.
- Similarity results are candidates, not automatic duplicate decisions. A user confirms a relationship.
- Jira requires credentials in `JIRA_BASE_URL`, `JIRA_USERNAME`, and `JIRA_API_TOKEN`. The connection test and remote Jira calls have not been verified against a configured Jira site.
- Apache Spark is not installed or configured in this Windows environment. SQLite is the implemented local storage; do not claim Spark-backed storage.
- The project does not provide reviewed code snippets. Recommendations show resolution notes from historical incidents.
- The dashboard and API do not have authentication. Run them only on a trusted local machine; do not expose them to a network as-is.

## Project structure

```text
api/                    Optional FastAPI endpoints
automation/             Local notifications and optional Jira client
dashboard/              Streamlit user interface
data_processing/        CSV/XLSX validation and cleaning
database/               SQLite schema, migrations, and queries
dataset/                Synthetic demo data
duplicate_detection/    Trie index and similarity scoring
incident_processing/    Per-record and batch workflow
machine_learning/       Severity model training and prediction
recommendation/         Resolved-incident recommendations
tests/                  Unit and integration tests
```

## Run on Windows in VS Code

1. Open this folder (`AI_INCIDENT_INTELLIGENCE`) in VS Code.
2. Open **Terminal → New Terminal** and create/activate an environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Initialize the database and demo model:

   ```powershell
   python main.py
   ```

4. Start the dashboard:

   ```powershell
   python -m streamlit run dashboard/app.py
   ```

5. Use **Incident Processing** to process all records, review candidates and local alerts, and close planned work after verifying completion.

## Optional REST API

Run from the project folder:

```powershell
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the local API. It supports incident CRUD, processing one incident (`POST /api/incidents/{incident_id}/process`), and batch processing (`POST /api/process/batch?threshold=0.35`). Keep it bound to localhost.

## Verify the project

```powershell
python -m pytest -q
```

Tests use temporary databases for processor/API integration checks. `requirements.txt` includes the packages needed by the application and test client.
