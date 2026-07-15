"""Deterministic impact calculations for Code Agent findings."""


POOL_UTILIZATION_THRESHOLD_PCT = 100.0

# no of queries per request based on nesting depth
def _queries_per_request(nesting_depth: int, metrics: dict) -> int:
    orders = metrics["avg_orders_per_user"]
    items = metrics["avg_items_per_order"]
    if nesting_depth <= 0:
        return 1
    return round(orders * (items ** (nesting_depth - 1)))


def compute_impact(findings: list, metrics: dict) -> dict:
    """Convert findings and telemetry into deterministic projected metrics."""
    query_count = sum(
        _queries_per_request(finding.get("nesting_depth", 1), metrics)
        for finding in findings
    )

    # how many requests per second can the system serve at peak load,
    # given that each request takes p95_latency_ms
    p95_latency_ms = metrics["p95_latency_ms"]
    latency_seconds = p95_latency_ms / 1000
    request_rate = (
        metrics["peak_concurrent_users"] / latency_seconds
        if latency_seconds
        else 0
    )
    
    projected_qps = query_count * request_rate
    pool_size = metrics["connection_pool_size"]
    pool_utilization_pct = (
        metrics["peak_concurrent_users"] * query_count / pool_size * 100
        if pool_size
        else 0
    )
    latency_estimate_ms = p95_latency_ms * max(query_count, 1)
    endpoint = findings[0].get("endpoint", "unknown") if findings else "unknown"

    return {
        "endpoint": endpoint,
        "projected_query_count": query_count,
        "projected_qps": round(projected_qps, 2),
        "pool_utilization_pct": round(pool_utilization_pct, 2),
        "latency_estimate_ms": round(latency_estimate_ms, 2),
        "threshold_breached": pool_utilization_pct >= POOL_UTILIZATION_THRESHOLD_PCT,
    }
