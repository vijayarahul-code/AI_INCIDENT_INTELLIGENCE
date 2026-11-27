# Missing Features and Corrections

## Baseline Gap Analysis

This is the pre-correction assessment of the existing project against the supplied company reference. Statuses below describe observed code and baseline executions, not a claim that the complete acceptance workflow has passed. This document will be updated after the corrections and regression tests.

| Area | Baseline status | Evidence | Required correction |
|---|---|---|---|
| Excel/CSV source ingestion | Partial | `load_incident_file` reads CSV and XLSX. UI advertises XLS, but `xlrd` is not installed. No upload row/column counts or robust empty/corrupt-file handling. | Support CSV/XLSX reliably; either install/test XLS support or remove `.xls` from the UI; show validation, cleaning, valid/invalid counts and preview before import. |
| Pandas cleaning | Partial | Normalizes title/description and categories and fills nulls. Intentional invalid severity/date and duplicate IDs were reported by validation but remained in cleaned output. Original description is overwritten; assigned-team whitespace is not normalized. | Preserve source text; normalize a separate field; produce explicit valid and rejected records and reasons; standardize and validate severity/date/required values; keep duplicates from importing. |
| Trie keyword lookup | Partial | Insert and prefix operations exist, but the dashboard imports the Trie without using it. Exact search currently returns prefix-linked incident IDs. | Define exact vs prefix behavior and use the index as part of incident processing, with tests for repeated IDs and phrase/token boundaries. |
| Apache Spark | Missing / environment-blocked | No PySpark module, Java, `JAVA_HOME`, or `spark-submit` found in Python 3.14.6 on this Windows host. | Keep Pandas as the default. Document Spark as unavailable here; only add an optional Spark adapter if a supported Java/Python/Spark runtime can be provisioned and tested. |
| Structured persistence | Implemented, partial schema | Existing SQLite DB has 24 incidents and six tables. It persists incidents, history, duplicate review decisions, solution records and notifications. | Add idempotent migrations for processing outcomes, duplicate relationships, planned-work metadata and notification read state without replacing the existing DB. |
| Per-record incident engine | Missing | No processing-engine module or UI action iterates all records and saves per-record results. | Implement batch processing with per-record success/failure, timings, duplicate candidates, severity prediction, history lookup and alert results. |
| Similar issue matching | Partial / incorrect candidates | TF-IDF plus overlap runs, but the supplied login/payment/server sample returned unrelated cross-category candidates. Scores can exceed 1.0. | Avoid stop-word-only overlap, bound scores to [0, 1], exclude self-comparisons, and test the supplied cases. |
| Duplicate review | Partial | UI lets a user mark a selected pair and stores a review row. No review history display, explicit relationship, duplicate incident status, original ID, or duplicate notification workflow. | Keep review decisions, expose history, and only create a relationship/status change after explicit confirmation; never merge or delete automatically. |
| Severity model | Implemented but weak and under-tested | 24 training rows: Critical 4, High 9, Medium 8, Low 3. TF-IDF is fit on training data after a stratified split, avoiding vectorizer leakage. Holdout: 6 rows, 16.7% accuracy; four representative descriptions all predicted High. | Report limitations honestly, add repeatable evaluation tests and human review/storage of predictions. Do not claim production accuracy. Improve data volume before asserting model quality. |
| Critical alerts | Partial | A notification service can insert Critical notifications when called; it is not connected to processing or dashboard controls. No deduplication/read-state UI or predicted-vs-confirmed distinction. | Connect alerts to processing, distinguish predicted from confirmed severity, display history and avoid repeated alerts where appropriate. |
| Historical recommendations | Partial | Recommender reads a CSV directly rather than historical incident rows in SQLite. It displays textual resolutions but does not record viewed/accepted recommendations. No code snippets exist. | Search resolved database incidents, show source metadata and similarity, and record review/acceptance. Report code-snippet suggestions as absent unless real snippets are supplied. |
| Planned incident automation | Missing | No planned resolution metadata, verification action, or controlled closure workflow. | Add expected-resolution tracking and require explicit resolution verification before closure; note that authentication/authorization is not present. |
| REST API | Missing | No FastAPI routes or API module. FastAPI and Uvicorn happen to be installed in the current interpreter but are absent from requirements. | Add an optional documented API with validated CRUD and process endpoints, SQLite integration and request tests. |
| SQLite lifecycle and safety | Implemented with remaining hardening | A context-managed fresh connection now commits/rolls back and closes; existing database file is preserved. Some dynamic SQL identifiers in filters/updates are interpolated. | Keep per-operation connections; validate dynamic field names; test transaction rollback and all new tables/methods. |
| Dashboard | Partial; pages render | All eight navigation sections load in the current browser. Upload does not block invalid rows, mutations do not consistently invalidate cached incident data, prediction is not stored/reviewed, and Settings has no Jira test/create workflow. | Validate user inputs and import outcomes, refresh cached views after writes, provide processing/review/notification workflows and meaningful settings controls. |
| Jira | Implemented but externally unverified | `JiraIntegration` reads `JIRA_BASE_URL`, `JIRA_USERNAME`, and `JIRA_API_TOKEN`; issue read/create/comment calls exist. No credentials are configured, and no live connection or issue creation can be verified. | Keep optional, display neutral unconfigured state and secure setup instructions, add a real test-connection action, and do not claim remote behavior without credentials. |
| End-to-end acceptance | Not yet run | The baseline test suite is 6/6, but it does not cover upload-to-processing-to-alert-to-analytics persistence. | Add isolated end-to-end coverage using temporary sample files and a temporary SQLite DB; retain the production database unchanged. |

## Baseline Verification

- `python -m pytest -v`: **6 passed** on Python 3.14.6.
- Dataset size/class balance: **24 rows**, High 9, Medium 8, Critical 4, Low 3.
- Current holdout evaluation: **6 test rows, 16.7% accuracy**; class-level recall is 0 for Critical, Medium and Low.
- Four representative prediction inputs: all predicted High; probabilities were low-confidence (maximum roughly 0.38–0.41).
- Existing `incident_intelligence.db`: **24 incidents**; schema inspected without deleting or recreating it.
- Supplied similarity sample: unrelated pairs were returned as potential matches; several scores were inflated above intuitive TF-IDF similarity by token-overlap scoring.
- Spark prerequisites: PySpark, Java, `JAVA_HOME`, and `spark-submit` unavailable.
- Streamlit browser smoke test: all eight sidebar destinations rendered without uncaught errors after the earlier callback-signature correction.

## Correction Order

1. Fix and test cleaning, file parsing, exact/prefix Trie behavior, and duplicate-score precision.
2. Add a reusable per-record processing service and persist its outcomes and explicit duplicate decisions.
3. Connect upload, processing, prediction review, duplicate review, recommendations and alerts to the dashboard.
4. Add an optional FastAPI surface and API tests if it remains compatible with the local project environment.
5. Re-run the acceptance checks, then finalize the architecture, functionality, end-to-end and final project reports with observed status and blockers.

## Implementation Update — 2026-11-27

Implemented during the project completion pass:

- Single-incident processing now builds the Trie and similarity comparison context from every stored incident, then processes only the requested incident.
- Similarity scoring now uses stop-word-filtered, normalized tokens and bounded cosine/token-Dice scores. Regression coverage checks relevant login pairs and unrelated sample incidents.
- The dashboard now has an Incident Processing page for batch processing, saved-result summaries, notification history, and marking alerts read.
- Planned incidents can record an expected resolution date. Closure requires a user to affirm the work was verified; this is a manual safety check, not unattended auto-close.
- Uploads now parse the in-memory uploaded file, accept only CSV/XLSX, and refresh the cached incident list after import. Invalid rows are reported and excluded by the cleaner.
- New manual IDs use the next numeric INC suffix rather than the current row count, and required fields are checked.
- The optional API now has a batch-processing route. Jira Settings has a connection-test button when environment credentials exist.
- README setup, API usage, local-only security, model limitations, Spark status, Jira status, and recommendation limits are documented. HTTPX2 is declared for API tests.

Verification in this environment:

- Python compile check: passed for the edited processing, dashboard, API, and similarity modules.
- Focused cleaning/database/duplicate/processor/recommendation tests: **12 passed**.
- The API test client initially stalled with deprecated `httpx`. After declaring and installing `httpx2`, both API tests passed; the full suite finished with **14 passed**.
- Existing database files were not intentionally reset. Test databases and temporary files are isolated under `.test-tmp`.

Still incomplete or externally blocked relative to the supplied architecture diagram:

- Spark storage is unavailable; SQLite remains the working storage backend.
- The small synthetic severity dataset is insufficient for dependable classification; predictions require human review.
- Jira behavior is not remotely verified because credentials/site access are not configured.
- No source-provided, reviewed code snippets exist for solution recommendations.
- Planned closure requires explicit user verification rather than automatically closing by date.
- The dashboard/API have no authentication and are for local demonstration only.

Do not present the remaining items as implemented. The project is a more complete local demo, but it is not a fully production-ready implementation of every diagram item.