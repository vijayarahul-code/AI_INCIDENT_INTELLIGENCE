from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests


class JiraIntegration:
    def __init__(self, base_url: Optional[str] = None, username: Optional[str] = None, api_token: Optional[str] = None):
        self.base_url = base_url or os.getenv("JIRA_BASE_URL")
        self.username = username or os.getenv("JIRA_USERNAME")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN")

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.username and self.api_token)

    def get_auth(self) -> Optional[tuple[str, str]]:
        if not self.is_configured:
            return None
        return (self.username, self.api_token)

    def test_connection(self) -> Dict[str, Any]:
        if not self.is_configured:
            raise ValueError("Jira credentials are not configured.")
        response = requests.get(
            f"{self.base_url.rstrip('/')}/rest/api/2/myself",
            auth=self.get_auth(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def create_issue(self, project_key: str, summary: str, description: str, issue_type: str = "Task") -> Dict[str, Any]:
        if not self.is_configured:
            raise ValueError("Jira credentials are not configured. Skip integration if no environment variables are available.")

        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
            }
        }
        response = requests.post(
            f"{self.base_url}/rest/api/2/issue",
            json=payload,
            auth=self.get_auth(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        if not self.is_configured:
            raise ValueError("Jira credentials are not configured.")
        response = requests.get(
            f"{self.base_url}/rest/api/2/issue/{issue_key}",
            auth=self.get_auth(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def add_comment(self, issue_key: str, comment: str) -> Dict[str, Any]:
        if not self.is_configured:
            raise ValueError("Jira credentials are not configured.")
        payload = {"body": comment}
        response = requests.post(
            f"{self.base_url}/rest/api/2/issue/{issue_key}/comment",
            json=payload,
            auth=self.get_auth(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
