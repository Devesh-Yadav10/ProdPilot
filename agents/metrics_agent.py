"""Deterministic loader for synthetic production telemetry."""

import json
from pathlib import Path


METRICS_PATH = Path(__file__).parent.parent / "data" / "synthetic_metrics.json"
RELEVANT_FIELDS = (
    "avg_orders_per_user",
    "avg_items_per_order",
    "connection_pool_size",
    "p95_latency_ms",
    "peak_concurrent_users",
)


def load_metrics() -> dict:
    """Load the relevant synthetic telemetry fields from disk."""
    with METRICS_PATH.open(encoding="utf-8") as metrics_file:
        data = json.load(metrics_file)
    return {field: data[field] for field in RELEVANT_FIELDS}


def get_metrics_for_findings(findings: list[dict]) -> dict:
    """Return deterministic metrics for the supplied findings."""
    return load_metrics()


def get_relevant_metrics(finding_types: list[str]) -> dict:
    """Return metrics relevant to the supplied finding types."""
    return load_metrics()
