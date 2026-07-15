from agents.metrics_agent import load_metrics
from calculator import compute_impact


def test_known_nested_query_breaches_pool_threshold() -> None:
    findings = [
        {
            "file": "orders.py",
            "line": 4,
            "pattern_type": "nested_query",
            "nesting_depth": 2,
            "snippet": "product = Product.query.get(item.product_id)",
        }
    ]

    result = compute_impact(findings, load_metrics())

    assert result["endpoint"] == "unknown"
    assert result["projected_query_count"] == 15
    assert result["projected_qps"] == 100000.0
    assert result["pool_utilization_pct"] == 75000.0
    assert result["latency_estimate_ms"] == 2250
    assert result["threshold_breached"] is True
