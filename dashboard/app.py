from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from automation.jira_integration import JiraIntegration
from automation.notifications import NotificationService
from data_processing.cleaning import clean_incident_dataframe, load_incident_file, validate_incident_file
from database.db import DBManager
from duplicate_detection.similarity import describe_keyword_overlap, find_potential_duplicates
from duplicate_detection.trie import Trie
from machine_learning.predict import predict_severity
from recommendation.solution_engine import recommend_solutions
from incident_processing.processor import IncidentProcessor

st.set_page_config(page_title="Incident Intelligence", page_icon="📊", layout="wide")

ROOT = Path(__file__).resolve().parent.parent


@st.cache_resource
def get_db() -> DBManager:
    db = DBManager()
    db.initialize_database()
    db.ensure_demo_seed_data()
    return db


@st.cache_data
def get_incidents_df() -> pd.DataFrame:
    db = get_db()
    rows = db.get_incidents()
    if not rows:
        return pd.DataFrame(columns=["incident_id", "incident_title", "incident_description", "category", "severity", "status", "assigned_team", "created_date", "resolution_details"])
    data = [dict(row) for row in rows]
    return pd.DataFrame(data)


def render_overview(db: DBManager):
    summary = db.get_summary()
    st.title("Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total incidents", summary["total_incidents"])
    col2.metric("Open incidents", summary["open_incidents"])
    col3.metric("Resolved incidents", summary["resolved_incidents"])
    col4.metric("Critical incidents", summary["critical_incidents"])
    col5.metric("Potential duplicates", summary["potential_duplicates"])

    df = get_incidents_df()
    if df.empty:
        st.info("No incident records available yet.")
        return

    severity_chart = df["severity"].value_counts().reset_index()
    severity_chart.columns = ["Severity", "Count"]
    st.plotly_chart(px.bar(severity_chart, x="Severity", y="Count", color="Severity", title="Severity distribution"), width="stretch", alt="Incident counts by severity")

    category_chart = df["category"].value_counts().reset_index()
    category_chart.columns = ["Category", "Count"]
    st.plotly_chart(px.bar(category_chart, x="Category", y="Count", title="Category distribution"), width="stretch", alt="Incident counts by category")

    status_chart = df["status"].value_counts().reset_index()
    status_chart.columns = ["Status", "Count"]
    st.plotly_chart(px.pie(status_chart, names="Status", values="Count", title="Incident status"), width="stretch", alt="Share of incidents by status")

    if "created_date" in df.columns:
        df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce")
        trend = df.groupby(df["created_date"].dt.to_period("M")).size().reset_index()
        trend.columns = ["Month", "Count"]
        trend["Month"] = trend["Month"].astype(str)
        st.plotly_chart(px.line(trend, x="Month", y="Count", title="Incident trends over time"), width="stretch", alt="Incident counts over time")


def render_incident_management(db: DBManager):
    st.title("Incident Management")
    df = get_incidents_df()
    if df.empty:
        st.info("No incidents found in the database.")
        return

    search = st.text_input("Search incidents")
    filters = {
        "severity": st.selectbox("Filter by severity", ["", "Critical", "High", "Medium", "Low"]),
        "category": st.selectbox("Filter by category", ["", "Authentication", "Payment", "Database", "Infrastructure", "Performance", "Frontend", "Network"]),
        "status": st.selectbox("Filter by status", ["", "Open", "In Progress", "Resolved"]),
    }

    filtered = df.copy()
    if search:
        filtered = filtered[
            filtered["incident_title"].str.contains(search, case=False, na=False)
            | filtered["incident_description"].str.contains(search, case=False, na=False)
        ]
    for key, value in filters.items():
        if value:
            filtered = filtered[filtered[key] == value]

    st.dataframe(filtered, width="stretch", alt="Filtered incident records")

    with st.form("new_incident_form"):
        st.subheader("Add new incident")
        title = st.text_input("Incident title")
        description = st.text_area("Incident description")
        category = st.selectbox("Category", ["Authentication", "Payment", "Database", "Infrastructure", "Performance", "Frontend", "Network"])
        severity = st.selectbox("Severity", ["Critical", "High", "Medium", "Low"])
        status = st.selectbox("Status", ["Open", "In Progress", "Planned", "Resolved"])
        planned_date = st.date_input("Expected resolution date") if status == "Planned" else None
        assigned_team = st.text_input("Assigned team")
        created_date = st.date_input("Created date")
        resolution = st.text_area("Resolution details")
        submitted = st.form_submit_button("Save incident")
        if submitted:
            if not title.strip() or not description.strip() or not assigned_team.strip():
                st.error("Title, description, and assigned team are required.")
                return
            existing_ids = {str(row["incident_id"]) for row in db.get_incidents()}
            numeric_suffixes = [
                int(value.split("-")[-1]) for value in existing_ids
                if value.startswith("INC-") and value.split("-")[-1].isdigit()
            ]
            next_number = max(numeric_suffixes, default=1000) + 1
            incident_id = f"INC-{next_number}"
            try:
                db.insert_incident(
                incident_id=incident_id,
                incident_title=title,
                incident_description=description,
                category=category,
                severity=severity,
                status=status,
                assigned_team=assigned_team,
                created_date=str(created_date),
                resolution_details=resolution,
                source_type="Manual",
                is_demo=0,
                )
                if planned_date is not None:
                    db.update_incident(incident_id, {"planned_resolution_date": str(planned_date)})
                db.add_history(incident_id, "created", "Incident created through dashboard form")
                get_incidents_df.clear()
                st.success(f"Incident {incident_id} saved successfully.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def render_data_upload(db: DBManager):
    st.title("Data Upload")
    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            df = load_incident_file(uploaded_file)
            st.dataframe(df.head(20), width="stretch", alt="Preview of uploaded incident records")
            validation = validate_incident_file(df)
            st.write("Validation results")
            st.json(validation)
            if validation["missing_columns"]:
                st.error(f"Missing required columns: {validation['missing_columns']}")
            cleaned, stats = clean_incident_dataframe(df)
            st.write("Cleaning statistics")
            st.json(stats)
            if st.button("Import approved records", disabled=bool(validation["missing_columns"]) or cleaned.empty):
                for _, row in cleaned.iterrows():
                    incident_id = str(row.get("Incident ID", "")).strip()
                    if not incident_id:
                        continue
                    try:
                        db.insert_incident(
                            incident_id=incident_id,
                            incident_title=str(row.get("Incident Title", "")),
                            incident_description=str(row.get("Incident Description", "")),
                            category=str(row.get("Category", "General")),
                            severity=str(row.get("Severity", "Medium")),
                            status=str(row.get("Status", "Open")),
                            assigned_team=str(row.get("Assigned Team", "Unassigned")),
                            created_date=str(row.get("Created Date", "2024-01-01")),
                            resolution_details=str(row.get("Resolution Details", "")),
                            source_type="Uploaded",
                            is_demo=0,
                        )
                    except ValueError:
                        st.warning(f"Skipped duplicate or invalid record for ID {incident_id}.")
                st.success("Approved records imported.")
                get_incidents_df.clear()
                st.rerun()
        except Exception as exc:
            st.error(f"Upload failed: {exc}")


def render_duplicate_detection(db: DBManager):
    st.title("Duplicate Detection")
    incidents = db.get_incidents()
    if not incidents:
        st.info("No incidents to compare.")
        return

    incident_options = {row["incident_id"]: row["incident_title"] for row in incidents}
    source_id = st.selectbox("Select original incident", list(incident_options.keys()))
    source = db.get_incident(source_id)
    if source is None:
        return

    candidate_ids = [row["incident_id"] for row in incidents if row["incident_id"] != source_id]
    candidate_id = st.selectbox("Select candidate incident", candidate_ids)
    candidate = db.get_incident(candidate_id)
    if candidate is None:
        return

    similarity = find_potential_duplicates([source["incident_description"], candidate["incident_description"]], threshold=0.35)
    if similarity:
        score = similarity[0][2]
        overlap = describe_keyword_overlap(source["incident_description"], candidate["incident_description"])
        st.write(f"Similarity score: {score:.3f}")
        st.write(f"Matching keywords: {overlap}")
        if st.button("Mark as duplicate"):
            db.record_duplicate_review(source_id, candidate_id, score, "duplicate")
            st.success("Duplicate decision saved.")
        if st.button("Mark as not duplicate"):
            db.record_duplicate_review(source_id, candidate_id, score, "not_duplicate")
            st.info("Decision recorded as not duplicate.")
    else:
        st.info("No strong similarity detected for the selected pair.")


def render_severity_prediction(db: DBManager):
    st.title("AI Severity Prediction")
    description = st.text_area("Enter incident description")
    if st.button("Predict severity") and description:
        try:
            result = predict_severity(description)
            st.write(f"Predicted severity: {result['prediction']}")
            st.write(f"Confidence: {result['confidence']:.2%}")
            st.bar_chart(pd.DataFrame(result["probabilities"].items(), columns=["Severity", "Probability"]))
        except Exception as exc:
            st.error(f"Prediction failed: {exc}")


def render_solution_panel(db: DBManager):
    st.title("Solution Recommendations")
    incidents = db.get_incidents()
    if not incidents:
        st.info("No incidents available.")
        return
    incident_id = st.selectbox("Select incident for recommendations", [row["incident_id"] for row in incidents])
    incident = db.get_incident(incident_id)
    if incident is None:
        return
    recommendations = recommend_solutions(incident_id, incident["incident_description"], threshold=0.20, limit=5)
    if not recommendations:
        st.write("No sufficiently similar resolved incident found.")
    else:
        st.dataframe(pd.DataFrame(recommendations), width="stretch", alt="Resolved incidents with recommended solutions")


def render_analytics(db: DBManager):
    st.title("Analytics")
    df = get_incidents_df()
    if df.empty:
        st.info("No data available for analytics.")
        return
    st.plotly_chart(px.histogram(df, x="severity", color="category", title="Severity by category"), width="stretch", alt="Incidents by severity and category")
    st.plotly_chart(px.histogram(df, x="category", title="Category statistics"), width="stretch", alt="Incident counts by category")

    team_df = df.groupby("assigned_team").size().reset_index(name="Count")
    st.plotly_chart(px.bar(team_df, x="assigned_team", y="Count", title="Team-wise incident distribution"), width="stretch", alt="Incident counts by assigned team")


def render_settings(db: DBManager):
    st.title("Settings")
    st.number_input("Similarity threshold", min_value=0.0, max_value=1.0, value=0.35, step=0.05, key="similarity_threshold")
    jira = JiraIntegration()
    st.write("Jira configuration status:")
    st.write("Configured" if jira.is_configured else "Not configured. Local app continues without Jira credentials.")
    if jira.is_configured and st.button("Test Jira connection"):
        try:
            identity = jira.test_connection()
            st.success(f"Connected to Jira as {identity.get('displayName', identity.get('name', 'configured user'))}.")
        except Exception as exc:
            st.error(f"Jira connection failed: {exc}")
    elif not jira.is_configured:
        st.caption("Set JIRA_BASE_URL, JIRA_USERNAME, and JIRA_API_TOKEN in your environment to enable a connection test.")


def render_processing(db: DBManager):
    st.title("Incident Processing")
    threshold = st.slider("Duplicate similarity threshold", 0.0, 1.0, st.session_state.get("similarity_threshold", 0.35), 0.05, key="processing_threshold")
    if st.button("Process all incidents"):
        summary = IncidentProcessor(db).process_all(threshold=threshold)
        st.session_state["last_processing_summary"] = summary
    summary = st.session_state.get("last_processing_summary")
    if summary:
        st.json({key: value for key, value in summary.items() if key != "results"})
        st.dataframe(pd.DataFrame(summary["results"]), width="stretch", alt="Results from the latest processing run")
    st.subheader("Alert history")
    notifications = [dict(row) for row in db.get_notifications()]
    if notifications:
        st.dataframe(pd.DataFrame(notifications), width="stretch", alt="Saved incident alert history")
        unread = [item for item in notifications if not item["is_read"]]
        if unread:
            selected = st.multiselect("Mark alerts as read", [item["id"] for item in unread])
            if st.button("Mark selected read"):
                for notification_id in selected:
                    db.mark_notification_read(int(notification_id))
                st.rerun()
    else:
        st.info("No alerts have been recorded.")
    planned = [row for row in db.get_incidents(filters={"status": "Planned"})]
    if planned:
        st.subheader("Planned incident completion")
        st.caption("Confirm the planned work is complete before closing an incident.")
        selected_id = st.selectbox("Planned incident", [row["incident_id"] for row in planned])
        selected = db.get_incident(selected_id)
        if selected:
            st.write(f"Expected resolution: {selected['planned_resolution_date'] or 'Not set'}")
            confirmed = st.checkbox("I verified the planned work is complete", key=f"verify-{selected_id}")
            if st.button("Close verified incident", disabled=not confirmed):
                db.update_incident(selected_id, {"status": "Resolved"})
                db.add_history(selected_id, "planned_work_completed", "Closed after explicit dashboard verification")
                get_incidents_df.clear()
                st.success(f"{selected_id} marked Resolved.")
                st.rerun()


PAGES = {
    "Overview": render_overview,
    "Incident Processing": render_processing,
    "Incident Management": render_incident_management,
    "Data Upload": render_data_upload,
    "Duplicate Detection": render_duplicate_detection,
    "AI Severity Prediction": render_severity_prediction,
    "Solution Recommendations": render_solution_panel,
    "Analytics": render_analytics,
    "Settings": render_settings,
}


def main():
    db = get_db()
    with st.sidebar:
        st.title("Incident Intelligence")
        page = st.radio("Navigation", list(PAGES.keys()))

    PAGES[page](db)


if __name__ == "__main__":
    main()
