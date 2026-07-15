"""Small JSON-backed store for analyzed pull-request summaries."""

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

HISTORY_PATH = Path(__file__).parent / "data" / "analysis_history.json"
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


def record_analysis(pr_number: int | str, title: str, results: list[dict]) -> dict:
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
        "pr_number": str(pr_number),
        "title": title or "Untitled pull request",
        "severity": severity,
        "risk_summary": " ".join(summaries) if summaries else "No issues found.",
        "finding_count": len(findings),
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with _LOCK:
        history = _read()
        history = [item for item in history if item.get("pr_number") != str(pr_number)]
        history.insert(0, entry)
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY_PATH.open("w", encoding="utf-8") as history_file:
            json.dump(history[:100], history_file, indent=2)
    return entry


def load_history() -> list[dict]:
    with _LOCK:
        return _read()
