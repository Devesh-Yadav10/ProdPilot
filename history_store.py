"""Small JSON-backed store for analyzed pull-request summaries."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

HISTORY_PATH = Path(__file__).parent / "data" / "analysis_history.json"
ANALYSIS_LOG_PATH = Path(__file__).parent / "data" / "analysis_log.db"
_LOCK = Lock()


def _read() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        with HISTORY_PATH.open(encoding="utf-8") as history_file:
            data = json.load(history_file)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def record_analysis(
    repository: str, pr_number: int | str, title: str, results: list[dict]
) -> dict:
    findings = [finding for result in results for finding in result.get("findings", [])]
    severities = [result.get("risk", {}).get("severity", "low") for result in results]
    severity_order = {"high": 3, "medium": 2, "low": 1}
    severity = max(severities, key=lambda value: severity_order.get(value, 0), default="low")
    summaries = [
        result.get("risk", {}).get("risk_summary", "")
        for result in results
        if result.get("risk", {}).get("risk_summary")
    ]
    entry = {
        "repository": repository,
        "pr_number": str(pr_number),
        "title": title or "Untitled pull request",
        "severity": severity,
        "risk_summary": " ".join(summaries) if summaries else "No issues found.",
        "finding_count": len(findings),
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with _LOCK:
        history = _read()
        history = [
            item
            for item in history
            if not (
                item.get("repository") == repository
                and item.get("pr_number") == str(pr_number)
            )
        ]
        history.insert(0, entry)
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY_PATH.open("w", encoding="utf-8") as history_file:
            json.dump(history[:100], history_file, indent=2)
    return entry


def _processed_connection() -> sqlite3.Connection:
    ANALYSIS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(ANALYSIS_LOG_PATH)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_pull_requests (
            repository TEXT NOT NULL,
            pr_number INTEGER NOT NULL,
            head_sha TEXT NOT NULL,
            processed_at TIMESTAMP NOT NULL,
            PRIMARY KEY (repository, pr_number, head_sha)
        )
        """
    )
    return connection


def already_processed(repository: str, pr_number: int, head_sha: str) -> bool:
    with _LOCK, _processed_connection() as connection:
        row = connection.execute(
            """
            SELECT 1 FROM processed_pull_requests
            WHERE repository = ? AND pr_number = ? AND head_sha = ?
            """,
            (repository, pr_number, head_sha),
        ).fetchone()
    return row is not None


def record_processed(repository: str, pr_number: int, head_sha: str) -> None:
    with _LOCK, _processed_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO processed_pull_requests
                (repository, pr_number, head_sha, processed_at)
            VALUES (?, ?, ?, ?)
            """,
            (repository, pr_number, head_sha, datetime.now(timezone.utc).isoformat()),
        )


def load_history() -> list[dict]:
    with _LOCK:
        return _read()
