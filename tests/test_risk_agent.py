import os

import pytest

from agents.risk_agent import assess_risk


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_LLM_INTEGRATION") != "1",
    reason="Set RUN_LLM_INTEGRATION=1 to run live Groq integration tests",
)
def test_risk_agent_known_nested_query() -> None:
    findings = [{"pattern_type": "nested_query", "nesting_depth": 2}]
    impact = {
        "endpoint": "unknown",
        "projected_query_count": 15,
        "projected_qps": 100000.0,
        "pool_utilization_pct": 75000.0,
        "latency_estimate_ms": 2250,
        "threshold_breached": True,
    }

    result = assess_risk(findings, impact)

    assert result["severity"] in {"high", "medium", "low"}
    assert isinstance(result["threshold_breached"], bool)
    assert isinstance(result["risk_summary"], str)
