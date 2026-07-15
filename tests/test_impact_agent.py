import copy
import os

import pytest

from agents.code_agent import analyze_code
from agents.impact_agent import _fallback_impact, assess_business_impact
from agents.metrics_agent import load_metrics
from agents.recommendation_agent import suggest_fix
from agents.risk_agent import assess_risk
from calculator import compute_impact


SCENARIOS = {
    "bad_nested_loop": {
        "source": """
for order in user.orders:
    for item in order.items:
        product = Product.query.get(item.product_id)
""",
        "metrics": {},
    },
    "borderline_single_loop": {
        "source": """
for order in user.orders:
    product = Product.query.get(order.product_id)
""",
        "metrics": {"peak_concurrent_users": 2},
    },
    "clean_pr": {
        "source": """
def get_orders(user):
    return user.orders
""",
        "metrics": {},
    },
}


def run_scenario(name: str) -> dict:
    scenario = SCENARIOS[name]
    code_result = analyze_code(scenario["source"], f"{name}.py")
    metrics = load_metrics()
    metrics.update(copy.deepcopy(scenario["metrics"]))
    impact = compute_impact(code_result["findings"], metrics)
    risk = assess_risk(code_result["findings"], impact)
    snippet = code_result["findings"][0]["snippet"] if code_result["findings"] else ""
    recommendation = suggest_fix(risk["risk_summary"], snippet)
    business_impact = assess_business_impact(risk["risk_summary"])
    return {
        "code_agent": code_result,
        "calculator": impact,
        "risk_agent": risk,
        "recommendation_agent": recommendation,
        "impact_agent": business_impact,
    }


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_LLM_INTEGRATION") != "1",
    reason="Set RUN_LLM_INTEGRATION=1 to run the full LLM chain",
)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_full_chain_scenario_does_not_crash(scenario: str) -> None:
    result = run_scenario(scenario)
    assert set(result["impact_agent"]) == {
        "user_facing_impact",
        "cost_estimate",
        "narrative",
    }


def test_fallback_impact_covers_all_scenarios() -> None:
    summaries = [
        "1 nested query finding(s) project 15 queries/request, 100000.0 QPS, and 75000.0% pool utilization; the calculated threshold is breached.",
        "1 nested query finding(s) project 5 queries/request, 33.33 QPS, and 50.0% pool utilization; the calculated threshold is not breached.",
        "0 nested query finding(s) project 0 queries/request, 0 QPS, and 0% pool utilization; the calculated threshold is not breached.",
    ]
    for summary in summaries:
        result = _fallback_impact(summary)
        assert result["narrative"]
